#!/usr/bin/env python3
"""Ablation study runner for GenEC.

Runs GenEC under multiple configuration variants to measure the contribution
of each component (evolutionary mining, LLM naming, verification, fusion weight).

Usage:
    python -m evaluation.scripts.run_ablation \
        --benchmark-file evaluation/benchmarks/benchmark_classes.json \
        --output-dir evaluation/results \
        --max-classes 15
"""

import argparse
import json
import logging
import time
from pathlib import Path

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("GenEC.Ablation")


# ---------------------------------------------------------------------------
# Configuration variants
# ---------------------------------------------------------------------------

VARIANTS: dict[str, dict] = {
    "full": {},
    "no_evo": {
        "evolution": {"window_months": 0},
    },
    "no_llm": {
        "llm": {"api_key": "", "enabled": False},
        "naming": {"use_llm": False},
    },
    "no_verification": {
        "verification": {
            "enable_syntactic": False,
            "enable_semantic": False,
            "enable_behavioral": False,
        },
    },
    "high_static": {
        "fusion": {"alpha": 0.8},
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, overrides: dict) -> dict:
    """Recursively merge *overrides* into *base*, returning a new dict."""
    result = base.copy()
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _run_variant(variant_name: str, overrides: dict, class_file: str, repo_path: str):
    """Run a single configuration variant and return metrics."""
    from genec.core.pipeline import GenECPipeline

    logger.info("    Variant '%s' ...", variant_name)
    t0 = time.time()

    try:
        merged_overrides = _deep_merge({}, overrides)
        pipeline = GenECPipeline(config_overrides=merged_overrides)
        result = pipeline.run_full_pipeline(class_file, repo_path)
        elapsed = time.time() - t0

        # Collect per-cluster metrics
        cohesion_vals = []
        coupling_vals = []
        for c in result.all_clusters:
            cohesion_vals.append(_safe_float(c.internal_cohesion))
            coupling_vals.append(_safe_float(c.external_coupling))

        num_verified = len(result.verified_suggestions)
        num_clusters = len(result.all_clusters)
        verified_pct = (num_verified / num_clusters * 100.0) if num_clusters > 0 else 0.0

        return {
            "clusters_found": num_clusters,
            "num_verified": num_verified,
            "verified_pct": round(verified_pct, 2),
            "avg_cohesion": round(float(np.mean(cohesion_vals)), 4) if cohesion_vals else 0.0,
            "avg_coupling": round(float(np.mean(coupling_vals)), 4) if coupling_vals else 0.0,
            "execution_time": round(elapsed, 2),
            "original_lcom5": _safe_float(result.original_metrics.get("lcom5")),
            "original_tcc": _safe_float(result.original_metrics.get("tcc")),
        }

    except Exception as e:
        elapsed = time.time() - t0
        logger.error("    Variant '%s' failed: %s", variant_name, e, exc_info=True)
        return {
            "clusters_found": 0, "num_verified": 0, "verified_pct": 0.0,
            "avg_cohesion": 0.0, "avg_coupling": 0.0,
            "execution_time": round(elapsed, 2),
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run GenEC ablation study.")
    parser.add_argument("--benchmark-file", required=True, type=Path,
                        help="JSON listing benchmark classes (e.g. evaluation/benchmarks/benchmark_classes.json)")
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation/results"), help="Output directory")
    parser.add_argument("--max-classes", type=int, default=15, help="Max benchmark classes to evaluate (default: 15)")
    args = parser.parse_args()

    with open(args.benchmark_file) as f:
        benchmark = json.load(f)

    if isinstance(benchmark, dict):
        benchmark = benchmark.get("classes", benchmark.get("benchmarks", []))

    benchmark = benchmark[: args.max_classes]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    total = len(benchmark)
    logger.info("Ablation study: %d classes, %d variants", total, len(VARIANTS))

    # per_class[class_name][variant_name] = metrics dict
    per_class: dict[str, dict] = {}

    for idx, entry in enumerate(benchmark, 1):
        project_name = entry.get("project_name", "unknown")
        repo_path = entry["repo_path"]
        class_file = entry["class_file"]
        class_name = Path(class_file).stem

        logger.info("[%d/%d] %s (%s)", idx, total, class_name, project_name)

        per_class[class_name] = {"project_name": project_name}

        for variant_name, overrides in VARIANTS.items():
            metrics = _run_variant(variant_name, overrides, class_file, repo_path)
            per_class[class_name][variant_name] = metrics

    # ---------------------------------------------------------------------------
    # Aggregate across classes per variant
    # ---------------------------------------------------------------------------
    aggregate: dict[str, dict] = {}

    for variant_name in VARIANTS:
        clusters_list = []
        cohesion_list = []
        coupling_list = []
        verified_list = []
        time_list = []

        for class_name, data in per_class.items():
            v = data.get(variant_name, {})
            clusters_list.append(v.get("clusters_found", 0))
            cohesion_list.append(v.get("avg_cohesion", 0.0))
            coupling_list.append(v.get("avg_coupling", 0.0))
            verified_list.append(v.get("verified_pct", 0.0))
            time_list.append(v.get("execution_time", 0.0))

        def _s(vals):
            a = np.array(vals, dtype=float)
            return {"mean": round(float(np.mean(a)), 4),
                    "std": round(float(np.std(a)), 4),
                    "median": round(float(np.median(a)), 4)} if len(a) else {}

        aggregate[variant_name] = {
            "clusters_found": _s(clusters_list),
            "avg_cohesion": _s(cohesion_list),
            "avg_coupling": _s(coupling_list),
            "verified_pct": _s(verified_list),
            "execution_time": _s(time_list),
        }

    output = {
        "num_classes": total,
        "variants": list(VARIANTS.keys()),
        "per_class": per_class,
        "aggregate": aggregate,
    }

    out_file = args.output_dir / "ablation_results.json"
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2, default=str)

    logger.info("Ablation results saved to %s", out_file)

    # Print quick summary table
    print("\n" + "=" * 90)
    print(f"{'Variant':<20} {'Clusters':>10} {'Avg Cohesion':>12} {'Avg Coupling':>14} {'Verified%':>12} {'Time(s)':>10}")
    print("-" * 90)
    for vname, agg in aggregate.items():
        print(f"{vname:<20} "
              f"{agg['clusters_found'].get('mean', 0):>10.1f} "
              f"{agg['avg_cohesion'].get('mean', 0):>12.4f} "
              f"{agg['avg_coupling'].get('mean', 0):>14.4f} "
              f"{agg['verified_pct'].get('mean', 0):>12.1f} "
              f"{agg['execution_time'].get('mean', 0):>10.1f}")
    print("=" * 90)


if __name__ == "__main__":
    main()
