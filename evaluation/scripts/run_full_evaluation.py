#!/usr/bin/env python3
"""Main evaluation runner for GenEC benchmark evaluation.

Runs the full GenEC pipeline and a metric-only baseline on each benchmark class,
records per-class results, and generates aggregate statistics.

Usage:
    python -m evaluation.scripts.run_full_evaluation \
        --benchmark-file evaluation/configs/benchmark.json \
        --output-dir evaluation/results
"""

import argparse
import json
import logging
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("GenEC.Evaluation")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(value, default=0.0):
    """Convert to float, returning *default* on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _serialize(obj):
    """JSON-safe serialisation helper for dataclass / enum fields."""
    if hasattr(obj, "value"):  # enum
        return obj.value
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _serialize(v) for k, v in asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    return obj


# ---------------------------------------------------------------------------
# Baseline runner (metric-only: LCOM5/TCC + Louvain, no evo / LLM)
# ---------------------------------------------------------------------------

def run_baseline(class_file: str, repo_path: str, config_overrides: dict | None = None):
    """Run metric-only baseline: static dependencies + Louvain clustering.

    Returns a dict with cluster / metric information comparable to the full
    pipeline result.
    """
    from genec.core.pipeline import GenECPipeline

    overrides = {
        "evolution": {"window_months": 0},
        "clustering": {"algorithm": "louvain"},
        "llm": {"api_key": ""},
        "verification": {
            "enable_syntactic": False,
            "enable_semantic": False,
            "enable_behavioral": False,
        },
    }
    if config_overrides:
        overrides.update(config_overrides)

    try:
        pipeline = GenECPipeline(config_overrides=overrides)
        result = pipeline.run_full_pipeline(class_file, repo_path)
        clusters_data = [
            {
                "id": c.id,
                "size": len(c.member_names),
                "cohesion": _safe_float(c.internal_cohesion),
                "coupling": _safe_float(c.external_coupling),
                "members": c.member_names,
            }
            for c in result.all_clusters
        ]
        cluster_cohesions = [c.get("cohesion", 0.0) for c in clusters_data]
        return {
            "num_clusters": len(result.all_clusters),
            "clusters": clusters_data,
            "original_metrics": _serialize(result.original_metrics),
            "execution_time": result.execution_time,
            "avg_cluster_cohesion": sum(cluster_cohesions) / max(len(cluster_cohesions), 1),
        }
    except Exception as e:
        logger.error("Baseline failed for %s: %s", class_file, e, exc_info=True)
        return {"num_clusters": 0, "clusters": [], "original_metrics": {}, "execution_time": 0.0, "error": str(e)}


# ---------------------------------------------------------------------------
# Full pipeline runner
# ---------------------------------------------------------------------------

def run_genec(class_file: str, repo_path: str, config_file: str | None = None):
    """Run the full GenEC pipeline and return a structured result dict."""
    from genec.core.pipeline import GenECPipeline

    try:
        kwargs = {}
        if config_file:
            kwargs["config_file"] = config_file
        pipeline = GenECPipeline(**kwargs)
        result = pipeline.run_full_pipeline(class_file, repo_path)

        suggestions_data = []
        for s in result.suggestions:
            suggestions_data.append({
                "cluster_id": s.cluster_id,
                "proposed_class_name": s.proposed_class_name,
                "rationale": s.rationale,
                "confidence_score": _safe_float(s.confidence_score),
                "quality_tier": s.quality_tier if s.quality_tier else None,
                "members": s.cluster.member_names if s.cluster else [],
            })

        return {
            "num_clusters": len(result.all_clusters),
            "num_filtered": len(result.filtered_clusters),
            "num_verified": len(result.verified_suggestions),
            "suggestions": suggestions_data,
            "original_metrics": _serialize(result.original_metrics),
            "graph_metrics": _serialize(result.graph_metrics),
            "execution_time": result.execution_time,
            "avg_confidence": result.avg_confidence,
            "clusters": [
                {
                    "id": c.id,
                    "size": len(c.member_names),
                    "cohesion": _safe_float(c.internal_cohesion),
                    "coupling": _safe_float(c.external_coupling),
                    "quality_tier": c.quality_tier.value if c.quality_tier else None,
                    "members": c.member_names,
                }
                for c in result.all_clusters
            ],
            "avg_cluster_cohesion": (
                sum(_safe_float(c.internal_cohesion) for c in result.all_clusters)
                / max(len(result.all_clusters), 1)
            ),
        }
    except Exception as e:
        logger.error("GenEC pipeline failed for %s: %s", class_file, e, exc_info=True)
        return {
            "num_clusters": 0, "num_filtered": 0, "num_verified": 0,
            "suggestions": [], "original_metrics": {}, "graph_metrics": {},
            "execution_time": 0.0, "avg_confidence": 0.0, "clusters": [],
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Aggregate statistics
# ---------------------------------------------------------------------------

def compute_aggregate(per_class_results: dict) -> dict:
    """Compute summary statistics across all benchmark classes."""
    genec_clusters = []
    baseline_clusters = []
    lcom5_values = []
    coupling_values = []
    exec_times = []
    verified_counts = []
    confidence_scores = []

    for class_name, data in per_class_results.items():
        genec = data.get("genec", {})
        baseline = data.get("baseline", {})

        genec_clusters.append(genec.get("num_clusters", 0))
        baseline_clusters.append(baseline.get("num_clusters", 0))

        orig = genec.get("original_metrics", {})
        lcom5_values.append(_safe_float(orig.get("lcom5")))
        coupling_values.append(_safe_float(orig.get("external_coupling")))
        exec_times.append(genec.get("execution_time", 0.0))
        verified_counts.append(genec.get("num_verified", 0))
        confidence_scores.append(genec.get("avg_confidence", 0.0))

    def _stats(vals):
        arr = np.array(vals, dtype=float)
        if len(arr) == 0:
            return {"mean": 0.0, "std": 0.0, "median": 0.0, "min": 0.0, "max": 0.0}
        return {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "median": float(np.median(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
        }

    error_count = sum(1 for d in per_class_results.values() if d.get("genec", {}).get("error"))

    return {
        "num_classes": len(per_class_results),
        "error_count": error_count,
        "genec_clusters": _stats(genec_clusters),
        "baseline_clusters": _stats(baseline_clusters),
        "lcom5": _stats(lcom5_values),
        "coupling": _stats(coupling_values),
        "execution_time": _stats(exec_times),
        "verified_count": _stats(verified_counts),
        "avg_confidence": _stats(confidence_scores),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run full GenEC evaluation on benchmark classes.")
    parser.add_argument("--benchmark-file", required=True, type=Path, help="JSON file listing benchmark classes")
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation/results"), help="Output directory for results")
    parser.add_argument("--config", type=str, default=None, help="Path to GenEC config YAML (optional)")
    parser.add_argument("--skip-existing", action="store_true", help="Skip classes that already have result files")
    args = parser.parse_args()

    # Load benchmark
    with open(args.benchmark_file) as f:
        benchmark = json.load(f)

    if isinstance(benchmark, dict):
        benchmark = benchmark.get("classes", benchmark.get("benchmarks", []))

    args.output_dir.mkdir(parents=True, exist_ok=True)

    per_class_results = {}
    total = len(benchmark)

    for idx, entry in enumerate(benchmark, 1):
        project_name = entry.get("project_name", "unknown")
        repo_path = entry["repo_path"]
        class_file = entry["class_file"]
        class_name = Path(class_file).stem

        result_file = args.output_dir / f"{class_name}.json"
        if args.skip_existing and result_file.exists():
            logger.info("[%d/%d] Skipping %s (result exists)", idx, total, class_name)
            with open(result_file) as f:
                per_class_results[class_name] = json.load(f)
            continue

        logger.info("[%d/%d] Evaluating %s from %s", idx, total, class_name, project_name)

        # Run GenEC full pipeline
        logger.info("  Running GenEC full pipeline...")
        t0 = time.time()
        genec_result = run_genec(class_file, repo_path, args.config)
        genec_wall = time.time() - t0
        logger.info("  GenEC completed in %.1fs (%d clusters, %d verified)",
                     genec_wall, genec_result["num_clusters"], genec_result.get("num_verified", 0))

        # Run baseline
        logger.info("  Running baseline (metric-only)...")
        t0 = time.time()
        baseline_result = run_baseline(class_file, repo_path)
        baseline_wall = time.time() - t0
        logger.info("  Baseline completed in %.1fs (%d clusters)",
                     baseline_wall, baseline_result["num_clusters"])

        class_data = {
            "project_name": project_name,
            "class_file": class_file,
            "commit_sha": entry.get("commit_sha", ""),
            "genec": genec_result,
            "baseline": baseline_result,
        }

        # Save per-class result
        with open(result_file, "w") as f:
            json.dump(class_data, f, indent=2, default=str)
        logger.info("  Saved %s", result_file)

        per_class_results[class_name] = class_data

    # Aggregate
    aggregate = compute_aggregate(per_class_results)
    aggregate["per_class"] = {k: {"project": v.get("project_name", ""),
                                   "genec_clusters": v.get("genec", {}).get("num_clusters", 0),
                                   "baseline_clusters": v.get("baseline", {}).get("num_clusters", 0)}
                              for k, v in per_class_results.items()}

    agg_file = args.output_dir / "aggregate_results.json"
    with open(agg_file, "w") as f:
        json.dump(aggregate, f, indent=2, default=str)

    logger.info("Aggregate results saved to %s", agg_file)
    logger.info("Evaluation complete: %d classes processed.", len(per_class_results))


if __name__ == "__main__":
    main()
