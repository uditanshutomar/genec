#!/usr/bin/env python3
"""Run GenEC with different alpha values to find optimal static/evolutionary weight."""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

ALPHA_VALUES = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]


def run_alpha_sensitivity(benchmark_file: str, output_dir: str, max_classes: int = 20):
    """Run GenEC with each alpha value and collect metrics."""
    from genec.core.pipeline import GenECPipeline

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    benchmark = json.loads(Path(benchmark_file).read_text())
    classes = benchmark.get("classes", [])[:max_classes]

    results = {}

    for alpha in ALPHA_VALUES:
        logger.info(f"\n{'='*60}")
        logger.info(f"Running with alpha={alpha}")
        logger.info(f"{'='*60}")

        alpha_results = []
        overrides = {"fusion": {"alpha": alpha}}

        for i, cls in enumerate(classes):
            class_file = cls.get("file_path", "")
            repo_path = cls.get("repo_path", "")
            class_name = cls.get("class_name", f"class_{i}")

            logger.info(f"  [{i+1}/{len(classes)}] {class_name} (alpha={alpha})")

            try:
                pipeline = GenECPipeline(config_overrides=overrides)
                start = time.time()
                result = pipeline.run_full_pipeline(class_file, repo_path)
                elapsed = time.time() - start

                alpha_results.append({
                    "class_name": class_name,
                    "clusters_found": len(result.all_clusters),
                    "clusters_filtered": len(result.filtered_clusters),
                    "suggestions": len(result.suggestions),
                    "verified": len(result.verified_suggestions),
                    "execution_time": round(elapsed, 2),
                })
            except Exception as e:
                logger.error(f"  Failed: {e}")
                alpha_results.append({
                    "class_name": class_name,
                    "error": str(e),
                })

        total = len(alpha_results)
        succeeded = [r for r in alpha_results if "error" not in r]

        results[str(alpha)] = {
            "alpha": alpha,
            "per_class": alpha_results,
            "summary": {
                "total_classes": total,
                "succeeded": len(succeeded),
                "total_clusters": sum(r.get("clusters_found", 0) for r in succeeded),
                "total_suggestions": sum(r.get("suggestions", 0) for r in succeeded),
                "total_verified": sum(r.get("verified", 0) for r in succeeded),
                "avg_time": round(sum(r.get("execution_time", 0) for r in succeeded) / max(len(succeeded), 1), 2),
            },
        }

    # Save results
    out_file = output_path / "alpha_sensitivity_results.json"
    out_file.write_text(json.dumps(results, indent=2))
    logger.info(f"\nResults saved to {out_file}")

    # Print summary table
    print(f"\n{'Alpha':<8} {'Classes':<10} {'Clusters':<10} {'Suggestions':<13} {'Verified':<10} {'Avg Time':<10}")
    print("-" * 61)
    for alpha_str, data in results.items():
        s = data["summary"]
        print(f"{alpha_str:<8} {s['succeeded']:<10} {s['total_clusters']:<10} {s['total_suggestions']:<13} {s['total_verified']:<10} {s['avg_time']:<10}")


def main():
    parser = argparse.ArgumentParser(description="Run alpha sensitivity analysis")
    parser.add_argument("--benchmark-file", required=True, help="Path to benchmark JSON")
    parser.add_argument("--output-dir", default="evaluation/results", help="Output directory")
    parser.add_argument("--max-classes", type=int, default=20, help="Max classes to evaluate")
    args = parser.parse_args()

    run_alpha_sensitivity(args.benchmark_file, args.output_dir, args.max_classes)


if __name__ == "__main__":
    main()
