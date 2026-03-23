#!/usr/bin/env python3
"""Deep analysis of GenEC results against RefactoringMiner ground truth.

For every ground truth Extract Class refactoring, finds the best-matching
GenEC suggestion, computes Jaccard similarity at multiple thresholds, and
categorises mismatches.

Usage:
    python -m evaluation.scripts.analyze_ground_truth \
        --ground-truth-file evaluation/ground_truth/ground_truth.json \
        --results-dir evaluation/results \
        --output-file evaluation/results/ground_truth_analysis.json
"""

import argparse
import json
import logging
from pathlib import Path

from genec.evaluation.ground_truth_builder import GroundTruthBuilder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("GenEC.GroundTruthAnalysis")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jaccard(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _classify_mismatch(gt_members: set, suggestion_members: set, jaccard: float) -> str:
    """Categorise the type of mismatch between ground truth and suggestion.

    Categories:
        - naming_only:        Jaccard >= 0.8 (members essentially match)
        - partial_overlap:    0.3 <= Jaccard < 0.8
        - behavioral_vs_data: Overlap exists but one is primarily methods,
                              the other primarily fields
        - no_match:           Jaccard < 0.3
    """
    if jaccard >= 0.8:
        return "naming_only"

    if jaccard < 0.3:
        return "no_match"

    # Check for a behavioural vs data split
    gt_methods = {m for m in gt_members if "(" in m}
    gt_fields = gt_members - gt_methods
    sg_methods = {m for m in suggestion_members if "(" in m}
    sg_fields = suggestion_members - sg_methods

    gt_method_pct = len(gt_methods) / max(len(gt_members), 1)
    sg_method_pct = len(sg_methods) / max(len(suggestion_members), 1)

    # If one side is >70 % methods and the other <30 % methods, it is a
    # behavioural-vs-data split.
    if (gt_method_pct > 0.7 and sg_method_pct < 0.3) or (
        sg_method_pct > 0.7 and gt_method_pct < 0.3
    ):
        return "behavioral_vs_data"

    return "partial_overlap"


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def analyze(
    ground_truth_entries: list[dict],
    per_class_data: dict[str, dict],
    thresholds: list[float],
) -> dict:
    """Perform detailed ground truth analysis.

    Returns a dict with:
      - per_case:   list of per-ground-truth-case detail dicts
      - thresholds: {threshold -> {precision, recall, f1}}
      - category_distribution: counts per mismatch category
    """
    per_case_results = []
    category_counts = {"naming_only": 0, "partial_overlap": 0, "behavioral_vs_data": 0, "no_match": 0}

    # Map: class stem -> GenEC suggestions
    class_suggestions: dict[str, list[dict]] = {}
    for cname, data in per_class_data.items():
        suggestions = data.get("genec", {}).get("suggestions", [])
        class_suggestions[cname] = suggestions

    for gt in ground_truth_entries:
        source_class = gt.get("source_class", "")
        extracted_class = gt.get("extracted_class", "")
        gt_members = set(gt.get("extracted_members", []))
        commit_sha = gt.get("commit_sha", "")

        # Find matching class in results (try simple stem matching)
        matching_key = None
        for cname in class_suggestions:
            if cname in source_class or source_class in cname:
                matching_key = cname
                break

        if matching_key is None:
            per_case_results.append({
                "source_class": source_class,
                "extracted_class": extracted_class,
                "commit_sha": commit_sha,
                "gt_members": sorted(gt_members),
                "best_match": None,
                "best_jaccard": 0.0,
                "category": "no_match",
                "thresholds": {str(t): False for t in thresholds},
            })
            category_counts["no_match"] += 1
            continue

        suggestions = class_suggestions[matching_key]

        # Find best matching suggestion
        best_suggestion = None
        best_jaccard = 0.0

        for s in suggestions:
            s_members = set(s.get("members", []))
            j = _jaccard(gt_members, s_members)
            if j > best_jaccard:
                best_jaccard = j
                best_suggestion = s

        # Threshold hits
        threshold_hits = {str(t): best_jaccard >= t for t in thresholds}

        # Classify mismatch
        if best_suggestion is not None:
            s_members = set(best_suggestion.get("members", []))
            category = _classify_mismatch(gt_members, s_members, best_jaccard)
        else:
            category = "no_match"

        category_counts[category] += 1

        case_result = {
            "source_class": source_class,
            "extracted_class": extracted_class,
            "commit_sha": commit_sha,
            "gt_members": sorted(gt_members),
            "best_match": {
                "proposed_class_name": best_suggestion.get("proposed_class_name", "") if best_suggestion else None,
                "members": sorted(best_suggestion.get("members", [])) if best_suggestion else [],
                "confidence": best_suggestion.get("confidence_score", 0.0) if best_suggestion else None,
            },
            "best_jaccard": round(best_jaccard, 4),
            "category": category,
            "thresholds": threshold_hits,
        }

        # Overlap detail
        if best_suggestion is not None:
            s_members = set(best_suggestion.get("members", []))
            case_result["overlap"] = {
                "intersection": sorted(gt_members & s_members),
                "gt_only": sorted(gt_members - s_members),
                "suggestion_only": sorted(s_members - gt_members),
            }

        per_case_results.append(case_result)

    # Aggregate P/R/F1 per threshold
    threshold_metrics = {}
    for t in thresholds:
        tp = sum(1 for c in per_case_results if c["thresholds"].get(str(t), False))
        fn = len(per_case_results) - tp
        # Per-class FP calculation
        fp = 0
        for cls, suggestions in class_suggestions.items():
            cls_tp = sum(1 for s in suggestions if s.get("matched", False))
            fp += len(suggestions) - cls_tp

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

        threshold_metrics[str(t)] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }

    return {
        "num_ground_truth_cases": len(ground_truth_entries),
        "num_classes_with_results": len(class_suggestions),
        "per_case": per_case_results,
        "thresholds": threshold_metrics,
        "category_distribution": category_counts,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Analyze GenEC results against ground truth.")
    parser.add_argument("--ground-truth-file", required=True, type=Path,
                        help="Ground truth JSON from GroundTruthBuilder")
    parser.add_argument("--results-dir", type=Path, default=Path("evaluation/results"),
                        help="Directory with per-class result JSONs")
    parser.add_argument("--output-file", type=Path, default=None,
                        help="Output file (default: <results-dir>/ground_truth_analysis.json)")
    args = parser.parse_args()

    if args.output_file is None:
        args.output_file = args.results_dir / "ground_truth_analysis.json"

    # Load ground truth
    builder = GroundTruthBuilder()
    gt_entries_raw = builder.load_ground_truth(str(args.ground_truth_file))
    # Convert to plain dicts for uniform processing
    gt_entries = [
        {
            "commit_sha": r.commit_sha,
            "source_class": r.source_class,
            "extracted_class": r.extracted_class,
            "extracted_members": r.extracted_members,
            "source_file": r.source_file,
            "extracted_file": r.extracted_file,
        }
        for r in gt_entries_raw
    ]
    logger.info("Loaded %d ground truth refactorings", len(gt_entries))

    # Load per-class results
    skip = {"aggregate_results.json", "ablation_results.json", "statistical_analysis.json",
            "ground_truth_analysis.json"}
    per_class: dict[str, dict] = {}
    for p in sorted(args.results_dir.glob("*.json")):
        if p.name in skip:
            continue
        try:
            with open(p) as f:
                per_class[p.stem] = json.load(f)
        except Exception as e:
            logger.warning("Could not load %s: %s", p, e)

    logger.info("Loaded %d per-class result files", len(per_class))

    # Analyse
    thresholds = [0.3, 0.5, 0.8]
    result = analyze(gt_entries, per_class, thresholds)

    # Save
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_file, "w") as f:
        json.dump(result, f, indent=2, default=str)
    logger.info("Analysis saved to %s", args.output_file)

    # Print summary
    print("\n" + "=" * 70)
    print("GROUND TRUTH ANALYSIS SUMMARY")
    print("=" * 70)
    print(f"Ground truth cases: {result['num_ground_truth_cases']}")
    print(f"Classes with results: {result['num_classes_with_results']}")
    print()
    print("Category distribution:")
    for cat, count in result["category_distribution"].items():
        print(f"  {cat:<25s} {count}")
    print()
    print(f"{'Threshold':<12} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print("-" * 44)
    for t_str, metrics in result["thresholds"].items():
        print(f"J >= {t_str:<7} {metrics['precision']:>10.3f} {metrics['recall']:>10.3f} {metrics['f1']:>10.3f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
