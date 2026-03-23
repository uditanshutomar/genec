#!/usr/bin/env python3
"""Run GenEC live evaluation on real God Classes from cloned repos."""

import json
import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger("evaluation")
logger.setLevel(logging.INFO)

# Benchmark classes with actual local paths
BENCHMARK = [
    # Commons IO
    {"project": "commons-io", "class_name": "IOUtils",
     "class_file": "src/main/java/org/apache/commons/io/IOUtils.java",
     "repo_path": "/tmp/commons-io"},
    {"project": "commons-io", "class_name": "FileUtils",
     "class_file": "src/main/java/org/apache/commons/io/FileUtils.java",
     "repo_path": "/tmp/commons-io"},
    {"project": "commons-io", "class_name": "FilenameUtils",
     "class_file": "src/main/java/org/apache/commons/io/FilenameUtils.java",
     "repo_path": "/tmp/commons-io"},
    # Commons Lang
    {"project": "commons-lang", "class_name": "StringUtils",
     "class_file": "src/main/java/org/apache/commons/lang3/StringUtils.java",
     "repo_path": "/tmp/commons-lang"},
    {"project": "commons-lang", "class_name": "ArrayUtils",
     "class_file": "src/main/java/org/apache/commons/lang3/ArrayUtils.java",
     "repo_path": "/tmp/commons-lang"},
    {"project": "commons-lang", "class_name": "NumberUtils",
     "class_file": "src/main/java/org/apache/commons/lang3/math/NumberUtils.java",
     "repo_path": "/tmp/commons-lang"},
    {"project": "commons-lang", "class_name": "DateUtils",
     "class_file": "src/main/java/org/apache/commons/lang3/time/DateUtils.java",
     "repo_path": "/tmp/commons-lang"},
    {"project": "commons-lang", "class_name": "SystemUtils",
     "class_file": "src/main/java/org/apache/commons/lang3/SystemUtils.java",
     "repo_path": "/tmp/commons-lang"},
    # Commons Collections
    {"project": "commons-collections", "class_name": "CollectionUtils",
     "class_file": "src/main/java/org/apache/commons/collections4/CollectionUtils.java",
     "repo_path": "/tmp/commons-collections"},
    {"project": "commons-collections", "class_name": "MapUtils",
     "class_file": "src/main/java/org/apache/commons/collections4/MapUtils.java",
     "repo_path": "/tmp/commons-collections"},
    {"project": "commons-collections", "class_name": "IteratorUtils",
     "class_file": "src/main/java/org/apache/commons/collections4/IteratorUtils.java",
     "repo_path": "/tmp/commons-collections"},
    # JFreeChart
    {"project": "jfreechart", "class_name": "XYPlot",
     "class_file": "src/main/java/org/jfree/chart/plot/XYPlot.java",
     "repo_path": "/tmp/jfreechart"},
    {"project": "jfreechart", "class_name": "CategoryPlot",
     "class_file": "src/main/java/org/jfree/chart/plot/CategoryPlot.java",
     "repo_path": "/tmp/jfreechart"},
    {"project": "jfreechart", "class_name": "PiePlot",
     "class_file": "src/main/java/org/jfree/chart/plot/pie/PiePlot.java",
     "repo_path": "/tmp/jfreechart"},
    {"project": "jfreechart", "class_name": "AbstractRenderer",
     "class_file": "src/main/java/org/jfree/chart/renderer/AbstractRenderer.java",
     "repo_path": "/tmp/jfreechart"},
    {"project": "jfreechart", "class_name": "ChartPanel",
     "class_file": "src/main/java/org/jfree/chart/swing/ChartPanel.java",
     "repo_path": "/tmp/jfreechart"},
    # Commons Math
    {"project": "commons-math", "class_name": "AccurateMath",
     "class_file": "commons-math-core/src/main/java/org/apache/commons/math4/core/jdkmath/AccurateMath.java",
     "repo_path": "/tmp/commons-math"},
    {"project": "commons-math", "class_name": "Dfp",
     "class_file": "commons-math-legacy-core/src/main/java/org/apache/commons/math4/legacy/core/dfp/Dfp.java",
     "repo_path": "/tmp/commons-math"},
    {"project": "commons-math", "class_name": "BOBYQAOptimizer",
     "class_file": "commons-math-legacy/src/main/java/org/apache/commons/math4/legacy/optim/nonlinear/scalar/noderiv/BOBYQAOptimizer.java",
     "repo_path": "/tmp/commons-math"},
    {"project": "commons-math", "class_name": "DSCompiler",
     "class_file": "commons-math-legacy/src/main/java/org/apache/commons/math4/legacy/analysis/differentiation/DSCompiler.java",
     "repo_path": "/tmp/commons-math"},
    # Commons Text
    {"project": "commons-text", "class_name": "TextStringBuilder",
     "class_file": "src/main/java/org/apache/commons/text/TextStringBuilder.java",
     "repo_path": "/tmp/commons-text"},
    {"project": "commons-text", "class_name": "StringLookupFactory",
     "class_file": "src/main/java/org/apache/commons/text/lookup/StringLookupFactory.java",
     "repo_path": "/tmp/commons-text"},
    {"project": "commons-text", "class_name": "StringSubstitutor",
     "class_file": "src/main/java/org/apache/commons/text/StringSubstitutor.java",
     "repo_path": "/tmp/commons-text"},
]


def _compute_suggestion_post_metrics(suggestion) -> dict:
    """Compute post-refactoring LCOM5/TCC for a single suggestion's modified original."""
    if not suggestion.modified_original_code:
        return {}
    try:
        import os
        import tempfile

        from genec.core.dependency_analyzer import DependencyAnalyzer
        from genec.metrics.cohesion_calculator import CohesionCalculator

        with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f:
            f.write(suggestion.modified_original_code)
            temp_file = f.name

        try:
            analyzer = DependencyAnalyzer()
            modified_deps = analyzer.analyze_class(temp_file)
            if modified_deps:
                calc = CohesionCalculator()
                post_metrics = calc.calculate_cohesion_metrics(modified_deps)
                return {
                    "post_lcom5": round(post_metrics.get("lcom5", 0), 4),
                    "post_tcc": round(post_metrics.get("tcc", 0), 4),
                }
        finally:
            os.unlink(temp_file)
    except Exception as e:
        logger.warning(f"Failed to compute per-suggestion post metrics: {e}")
    return {}


def run_single_class(entry: dict) -> dict:
    """Run GenEC on a single class and return results."""
    from genec.core.pipeline import GenECPipeline

    class_file = str(Path(entry["repo_path"]) / entry["class_file"])
    repo_path = entry["repo_path"]

    result_data = {
        "project": entry["project"],
        "class_name": entry["class_name"],
        "class_file": entry["class_file"],
    }

    try:
        # Cache LLM responses for reproducibility and cost savings
        cache_dir = str(Path("evaluation/results/llm_cache"))
        pipeline = GenECPipeline(
            config_overrides={
                "refactoring_application": {"enabled": False},
                "llm": {"cache_dir": cache_dir, "use_cache": True},
            }
        )

        start = time.time()
        result = pipeline.run_full_pipeline(class_file, repo_path)
        elapsed = time.time() - start

        result_data.update({
            "status": "success",
            "execution_time": round(elapsed, 1),
            "original_metrics": {
                "lcom5": round(result.original_metrics.get("lcom5", 0), 4),
                "tcc": round(result.original_metrics.get("tcc", 0), 4),
                "cbo": result.original_metrics.get("cbo", 0),
                "num_methods": result.original_metrics.get("num_methods", 0),
                "num_fields": result.original_metrics.get("num_fields", 0),
            },
            "clusters_found": len(result.all_clusters),
            "clusters_filtered": len(result.filtered_clusters),
            "clusters_rejected": len(result.all_clusters) - len(result.filtered_clusters),
            "filter_pass_rate": round(len(result.suggestions) / max(len(result.all_clusters), 1) * 100, 1),
            "suggestions_total": len(result.suggestions),
            "suggestions_verified": len(result.verified_suggestions),
            "suggestions": [
                {
                    "name": s.proposed_class_name,
                    "methods": len(s.cluster.get_methods()) if s.cluster else 0,
                    "verified": s.verification_status == "verified",
                    "confidence": s.confidence_score,
                    "rationale": s.rationale[:200] if s.rationale else None,
                    **_compute_suggestion_post_metrics(s),
                }
                for s in result.suggestions
            ],
        })

        # Post-refactoring metrics: what the class would look like after extraction
        original_methods = result.original_metrics.get("num_methods", 0)
        extracted_methods = sum(
            len(s.cluster.get_methods()) if s.cluster else 0
            for s in result.verified_suggestions
        )
        remaining_methods = max(original_methods - extracted_methods, 0)
        result_data["post_refactoring"] = {
            "methods_extracted": extracted_methods,
            "methods_remaining": remaining_methods,
            "extraction_coverage": round(extracted_methods / max(original_methods, 1) * 100, 1),
        }

        # Compute post-refactoring cohesion metrics on the modified original class
        if result.verified_suggestions:
            try:
                import os
                import tempfile

                from genec.core.dependency_analyzer import DependencyAnalyzer
                from genec.metrics.cohesion_calculator import CohesionCalculator

                # Use the last verified suggestion's modified original as a
                # reasonable approximation for the aggregate post-refactoring state
                last_verified = result.verified_suggestions[-1]
                if last_verified.modified_original_code:
                    with tempfile.NamedTemporaryFile(
                        suffix=".java", mode="w", delete=False
                    ) as f:
                        f.write(last_verified.modified_original_code)
                        temp_file = f.name

                    try:
                        analyzer = DependencyAnalyzer()
                        modified_deps = analyzer.analyze_class(temp_file)
                        if modified_deps:
                            calc = CohesionCalculator()
                            post_metrics = calc.calculate_cohesion_metrics(modified_deps)
                            result_data["post_refactoring"]["lcom5"] = round(
                                post_metrics.get("lcom5", 0), 4
                            )
                            result_data["post_refactoring"]["tcc"] = round(
                                post_metrics.get("tcc", 0), 4
                            )
                    finally:
                        os.unlink(temp_file)
            except Exception as e:
                logger.warning(f"Failed to compute post-refactoring metrics: {e}")

    except Exception as e:
        import traceback
        result_data.update({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()[-500:],
            "execution_time": 0,
        })

    return result_data


def main():
    output_dir = Path("evaluation/results/live_evaluation")
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    total_suggestions = 0
    total_verified = 0
    total_time = 0

    for i, entry in enumerate(BENCHMARK):
        logger.info(f"\n{'='*60}")
        logger.info(f"[{i+1}/{len(BENCHMARK)}] {entry['class_name']} ({entry['project']})")
        logger.info(f"{'='*60}")

        # Check file exists
        full_path = Path(entry["repo_path"]) / entry["class_file"]
        if not full_path.exists():
            logger.error(f"  File not found: {full_path}")
            all_results.append({"class_name": entry["class_name"], "status": "file_not_found"})
            continue

        result = run_single_class(entry)
        all_results.append(result)

        # Save per-class result
        class_file = output_dir / f"{entry['class_name']}.json"
        class_file.write_text(json.dumps(result, indent=2, default=str))

        # Print summary
        if result["status"] == "success":
            s = result["suggestions_total"]
            v = result["suggestions_verified"]
            t = result["execution_time"]
            total_suggestions += s
            total_verified += v
            total_time += t
            logger.info(f"  ✓ {v}/{s} verified in {t}s")
            for sg in result["suggestions"]:
                mark = "✓" if sg["verified"] else "✗"
                logger.info(f"    {mark} {sg['name']} ({sg['methods']} methods)")
        else:
            logger.error(f"  ✗ FAILED: {result.get('error', 'unknown')[:100]}")

    # Save aggregate results
    succeeded_results = [r for r in all_results if r.get("status") == "success"]
    total_clusters = sum(r.get("clusters_found", 0) for r in succeeded_results)
    aggregate = {
        "total_classes": len(BENCHMARK),
        "successful": len(succeeded_results),
        "failed": len([r for r in all_results if r.get("status") != "success"]),
        "total_clusters_found": total_clusters,
        "filter_pass_rate": round(total_suggestions / max(total_clusters, 1) * 100, 1),
        "total_suggestions": total_suggestions,
        "total_verified": total_verified,
        "verification_rate": round(total_verified / max(total_suggestions, 1) * 100, 1),
        "total_time": round(total_time, 1),
        "avg_time_per_class": round(total_time / max(len(BENCHMARK), 1), 1),
        "per_class": all_results,
    }

    agg_file = output_dir / "aggregate_results.json"
    agg_file.write_text(json.dumps(aggregate, indent=2, default=str))

    # Print final summary
    logger.info(f"\n{'='*60}")
    logger.info("EVALUATION COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Classes: {aggregate['successful']}/{aggregate['total_classes']} succeeded")
    logger.info(f"Suggestions: {aggregate['total_suggestions']} total, {aggregate['total_verified']} verified ({aggregate['verification_rate']}%)")
    logger.info(f"Total time: {aggregate['total_time']}s ({aggregate['avg_time_per_class']}s avg)")
    logger.info(f"Results saved to {output_dir}/")


if __name__ == "__main__":
    main()
