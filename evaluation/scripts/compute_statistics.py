#!/usr/bin/env python3
"""Statistical analysis for GenEC evaluation results.

Computes:
  - Wilcoxon signed-rank tests (GenEC vs baseline, paired by class)
  - Cliff's delta effect size
  - Bootstrap 95 % confidence intervals
  - P / R / F1 against ground truth at multiple Jaccard thresholds

Usage:
    python -m evaluation.scripts.compute_statistics \
        --results-dir evaluation/results \
        --ground-truth-file evaluation/ground_truth/ground_truth.json
"""

import argparse
import json
import logging
from pathlib import Path

import numpy as np
from scipy import stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("GenEC.Statistics")


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------

def wilcoxon_test(x: list[float], y: list[float]) -> dict:
    """Paired Wilcoxon signed-rank test.  Returns stat, p-value, and whether
    the result is significant at alpha = 0.05."""
    x_arr, y_arr = np.array(x, dtype=float), np.array(y, dtype=float)
    diffs = x_arr - y_arr

    # Remove zero differences (Wilcoxon requirement)
    nonzero = diffs[diffs != 0]
    if len(nonzero) < 2:
        return {"statistic": None, "p_value": 1.0, "significant": False, "n_nonzero": len(nonzero)}

    try:
        stat, p = stats.wilcoxon(nonzero)
    except ValueError:
        return {"statistic": None, "p_value": 1.0, "significant": False, "n_nonzero": len(nonzero)}

    return {
        "statistic": float(stat),
        "p_value": float(p),
        "significant": p < 0.05,
        "n_nonzero": int(len(nonzero)),
    }


def cliffs_delta(x: list[float], y: list[float]) -> dict:
    """Cliff's delta effect size (non-parametric).

    Returns delta in [-1, 1] and a magnitude label:
    negligible (|d| < 0.147), small, medium, large (|d| >= 0.474).
    """
    x_arr, y_arr = np.array(x, dtype=float), np.array(y, dtype=float)
    n_x, n_y = len(x_arr), len(y_arr)
    if n_x == 0 or n_y == 0:
        return {"delta": 0.0, "magnitude": "negligible"}

    more = sum(1 for xi in x_arr for yi in y_arr if xi > yi)
    less = sum(1 for xi in x_arr for yi in y_arr if xi < yi)
    delta = (more - less) / (n_x * n_y)

    abs_d = abs(delta)
    if abs_d < 0.147:
        mag = "negligible"
    elif abs_d < 0.33:
        mag = "small"
    elif abs_d < 0.474:
        mag = "medium"
    else:
        mag = "large"

    return {"delta": round(delta, 4), "magnitude": mag}


def bootstrap_ci(values: list[float], n_bootstrap: int = 10000, ci: float = 0.95) -> dict:
    """Bootstrap confidence interval for the mean."""
    arr = np.array(values, dtype=float)
    if len(arr) == 0:
        return {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}

    rng = np.random.default_rng(42)
    boot_means = np.array([
        np.mean(rng.choice(arr, size=len(arr), replace=True))
        for _ in range(n_bootstrap)
    ])

    alpha = (1 - ci) / 2
    lower = float(np.percentile(boot_means, 100 * alpha))
    upper = float(np.percentile(boot_means, 100 * (1 - alpha)))

    return {
        "mean": round(float(np.mean(arr)), 4),
        "ci_lower": round(lower, 4),
        "ci_upper": round(upper, 4),
    }


# ---------------------------------------------------------------------------
# Ground truth evaluation helpers
# ---------------------------------------------------------------------------

def _jaccard(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def precision_recall_f1(
    genec_suggestions: list[dict],
    ground_truth_entries: list[dict],
    source_class: str,
    threshold: float,
) -> dict:
    """Compute P / R / F1 for a single class at a given Jaccard threshold."""
    # Filter ground truth to this class
    gt_for_class = [
        g for g in ground_truth_entries
        if source_class in g.get("source_class", "")
    ]

    if not gt_for_class:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": 0}

    tp = 0
    matched_gt = set()

    for suggestion in genec_suggestions:
        s_members = set(suggestion.get("members", []))
        best_j = 0.0
        best_idx = -1
        for i, gt in enumerate(gt_for_class):
            if i in matched_gt:
                continue
            gt_members = set(gt.get("extracted_members", []))
            j = _jaccard(s_members, gt_members)
            if j > best_j:
                best_j = j
                best_idx = i
        if best_j >= threshold and best_idx >= 0:
            tp += 1
            matched_gt.add(best_idx)

    fp = len(genec_suggestions) - tp
    fn = len(gt_for_class) - len(matched_gt)

    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

    return {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
            "tp": tp, "fp": fp, "fn": fn}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Compute statistical analysis of GenEC results.")
    parser.add_argument("--results-dir", type=Path, default=Path("evaluation/results/live_evaluation"))
    parser.add_argument("--ground-truth-file", type=Path, default=None,
                        help="Ground truth JSON (from GroundTruthBuilder)")
    args = parser.parse_args()

    # Load aggregate results
    # Try results-dir directly first, then fall back to live_evaluation subdir
    agg_file = args.results_dir / "aggregate_results.json"
    if not agg_file.exists():
        agg_file = args.results_dir / "live_evaluation" / "aggregate_results.json"
    if not agg_file.exists():
        logger.error("aggregate_results.json not found in %s or %s/live_evaluation/", args.results_dir, args.results_dir)
        return

    with open(agg_file) as f:
        aggregate = json.load(f)

    # Load per-class results
    per_class_files = sorted(args.results_dir.glob("*.json"))
    per_class_files = [p for p in per_class_files if p.name not in (
        "aggregate_results.json", "ablation_results.json", "statistical_analysis.json")]

    per_class_data: dict[str, dict] = {}
    for pf in per_class_files:
        try:
            with open(pf) as f:
                per_class_data[pf.stem] = json.load(f)
        except Exception as e:
            logger.warning("Could not load %s: %s", pf, e)

    logger.info("Loaded %d per-class results", len(per_class_data))

    output: dict = {"num_classes": len(per_class_data)}

    # -----------------------------------------------------------------------
    # 1) Paired comparisons: GenEC vs baseline
    # -----------------------------------------------------------------------
    genec_clusters = []
    baseline_clusters = []
    genec_cohesion = []
    baseline_cohesion = []
    improvement_cohesion = []

    for cname, data in per_class_data.items():
        g = data.get("genec", {})
        b = data.get("baseline", {})
        genec_clusters.append(g.get("num_clusters", 0))
        baseline_clusters.append(b.get("num_clusters", 0))

        # Compute avg cluster cohesion from the clusters array
        g_clusters = g.get("clusters", [])
        b_clusters = b.get("clusters", [])
        g_cohesion = sum(c.get("cohesion", 0.0) for c in g_clusters) / max(len(g_clusters), 1) if g_clusters else 0.0
        b_cohesion = sum(c.get("cohesion", 0.0) for c in b_clusters) / max(len(b_clusters), 1) if b_clusters else 0.0
        genec_cohesion.append(float(g_cohesion))
        baseline_cohesion.append(float(b_cohesion))
        improvement_cohesion.append(g_cohesion - b_cohesion)

    comparisons = {}
    comparisons["clusters"] = {
        "wilcoxon": wilcoxon_test(genec_clusters, baseline_clusters),
        "cliffs_delta": cliffs_delta(genec_clusters, baseline_clusters),
        "genec_mean": round(float(np.mean(genec_clusters)), 4) if genec_clusters else 0.0,
        "baseline_mean": round(float(np.mean(baseline_clusters)), 4) if baseline_clusters else 0.0,
    }
    comparisons["cohesion_improvement"] = {
        "bootstrap_ci": bootstrap_ci(improvement_cohesion),
        "wilcoxon": wilcoxon_test(genec_cohesion, baseline_cohesion),
        "cliffs_delta": cliffs_delta(improvement_cohesion, [0.0] * len(improvement_cohesion)),
    }

    output["comparisons"] = comparisons

    # -----------------------------------------------------------------------
    # 2) Ground truth P/R/F1
    # -----------------------------------------------------------------------
    if args.ground_truth_file and args.ground_truth_file.exists():
        logger.info("Loading ground truth from %s", args.ground_truth_file)
        with open(args.ground_truth_file) as f:
            gt_data = json.load(f)

        gt_entries = gt_data.get("refactorings", [])
        thresholds = [0.3, 0.5, 0.8]

        gt_results: dict[str, dict] = {}
        for threshold in thresholds:
            all_prec, all_rec, all_f1 = [], [], []

            for cname, data in per_class_data.items():
                suggestions = data.get("genec", {}).get("suggestions", [])
                source_class = cname  # class stem as identifier
                prf = precision_recall_f1(suggestions, gt_entries, source_class, threshold)
                all_prec.append(prf["precision"])
                all_rec.append(prf["recall"])
                all_f1.append(prf["f1"])

            gt_results[f"threshold_{threshold}"] = {
                "precision": bootstrap_ci(all_prec),
                "recall": bootstrap_ci(all_rec),
                "f1": bootstrap_ci(all_f1),
            }

        output["ground_truth"] = gt_results
    else:
        logger.info("No ground truth file provided; skipping P/R/F1 computation.")

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------
    out_file = args.results_dir / "statistical_analysis.json"
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2, default=str)

    logger.info("Statistical analysis saved to %s", out_file)


if __name__ == "__main__":
    main()
