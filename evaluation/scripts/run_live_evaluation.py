#!/usr/bin/env python3
"""Run GenEC live evaluation on real God Classes from cloned repos."""

import json
import logging
import os
import sys
import tempfile
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
            "filter_pass_rate": round(len(result.filtered_clusters) / max(len(result.all_clusters), 1) * 100, 1),
            "suggestions_total": len(result.suggestions),
            "suggestions_verified": len(result.verified_suggestions),
            "suggestions": [
                {
                    "name": s.proposed_class_name,
                    "methods": s.cluster.get_methods() if s.cluster else [],
                    "fields": s.cluster.get_fields() if s.cluster else [],
                    "members": s.cluster.member_names if s.cluster else [],
                    "member_types": s.cluster.member_types if s.cluster else {},
                    "cluster_id": s.cluster.id if s.cluster else None,
                    "quality_tier": (s.cluster.quality_tier.value if s.cluster and hasattr(s.cluster, 'quality_tier') and s.cluster.quality_tier else
                                    s.quality_tier),
                    "quality_score": (s.cluster.quality_score if s.cluster and hasattr(s.cluster, 'quality_score') and s.cluster.quality_score
                                     else s.quality_score),
                    "quality_reasons": s.quality_reasons if s.quality_reasons else [],
                    "internal_cohesion": s.cluster.internal_cohesion if s.cluster else None,
                    "external_coupling": s.cluster.external_coupling if s.cluster else None,
                    "modularity": s.cluster.modularity if s.cluster else None,
                    "silhouette_score": s.cluster.silhouette_score if s.cluster else None,
                    "conductance": s.cluster.conductance if s.cluster else None,
                    "coverage": s.cluster.coverage if s.cluster else None,
                    "is_connected": s.cluster.is_connected if s.cluster else None,
                    "stability_score": s.cluster.stability_score if s.cluster else None,
                    "verified": getattr(s, 'verification_status', None) == "verified",
                    "verification_status": getattr(s, 'verification_status', None),
                    "confidence": s.confidence_score,
                    "rationale": s.rationale or getattr(s, 'reasoning', None),
                    "reasoning": s.reasoning,
                    "naming_votes": s.naming_votes,
                    "naming_agreement": s.naming_agreement,
                    **_compute_suggestion_post_metrics(s),
                }
                for s in result.suggestions
            ],
        })

        # Post-refactoring metrics: what the class would look like after extraction
        original_methods = result.original_metrics.get("num_methods", 0)
        # Use unique method counting to avoid double-counting shared helpers
        extracted_method_set = set()
        for s in result.verified_suggestions:
            if s.cluster:
                extracted_method_set.update(s.cluster.get_methods())
        extracted_methods = len(extracted_method_set)
        remaining_methods = max(original_methods - extracted_methods, 0)
        result_data["post_refactoring"] = {
            "methods_extracted": extracted_methods,
            "methods_remaining": remaining_methods,
            "extraction_coverage": round(extracted_methods / max(original_methods, 1) * 100, 1),
        }

        # Compute post-refactoring cohesion: what happens if ALL verified
        # suggestions are applied cumulatively?
        #
        # Each suggestion extracts different methods. We simulate cumulative
        # extraction by collecting all extracted method names, then computing
        # LCOM5/TCC on the original class minus those methods.
        if result.verified_suggestions:
            try:
                from genec.core.dependency_analyzer import DependencyAnalyzer
                from genec.metrics.cohesion_calculator import CohesionCalculator

                # Single-suggestion metrics (last verified, as before)
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
                            result_data["post_refactoring"]["single_extraction_lcom5"] = round(
                                post_metrics.get("lcom5", 0), 4
                            )
                            result_data["post_refactoring"]["single_extraction_tcc"] = round(
                                post_metrics.get("tcc", 0), 4
                            )
                    finally:
                        os.unlink(temp_file)

                # Cumulative metrics: compute what LCOM5 would be if ALL
                # verified suggestions were applied (all extracted methods removed)
                all_extracted_methods = set()
                for s in result.verified_suggestions:
                    if s.cluster:
                        all_extracted_methods.update(s.cluster.get_methods())

                # Parse original class to get full dependency info
                original_deps = None
                try:
                    orig_analyzer = DependencyAnalyzer()
                    original_path = str(Path(entry["repo_path"]) / entry["class_file"])
                    original_deps = orig_analyzer.analyze_class(original_path)
                except Exception:
                    pass

                if original_deps and all_extracted_methods:
                    # Build set of extracted method names (normalized)
                    extracted_names = {m.split("(")[0] for m in all_extracted_methods}

                    remaining_methods = [
                        m for m in original_deps.methods
                        if m.signature not in all_extracted_methods
                        and m.name not in extracted_names
                    ]

                    remaining_count = len(remaining_methods)
                    result_data["post_refactoring"]["cumulative_methods_remaining"] = remaining_count

                    if remaining_count >= 2:
                        # Create a filtered ClassDependencies for remaining methods
                        from copy import deepcopy
                        filtered_deps = deepcopy(original_deps)
                        filtered_deps.methods = remaining_methods

                        # Filter method_calls and field_accesses to remaining methods
                        remaining_sigs = {m.signature for m in remaining_methods}
                        remaining_names = {m.name for m in remaining_methods}
                        filtered_deps.method_calls = {
                            sig: calls for sig, calls in (original_deps.method_calls or {}).items()
                            if sig in remaining_sigs or sig.split("(")[0] in remaining_names
                        }
                        filtered_deps.field_accesses = {
                            sig: fields for sig, fields in (original_deps.field_accesses or {}).items()
                            if sig in remaining_sigs or sig.split("(")[0] in remaining_names
                        }

                        # Rebuild dependency matrix for remaining methods
                        from genec.core.dependency_analyzer import build_dependency_matrix
                        build_dependency_matrix(filtered_deps)  # Populates in-place

                        calc = CohesionCalculator()
                        cumulative_lcom5 = calc.calculate_lcom5(filtered_deps)
                        cumulative_tcc = calc.calculate_tcc(filtered_deps)
                        result_data["post_refactoring"]["cumulative_lcom5"] = round(cumulative_lcom5, 4)
                        result_data["post_refactoring"]["cumulative_tcc"] = round(cumulative_tcc, 4)
                    else:
                        result_data["post_refactoring"]["cumulative_lcom5"] = 0.0
                        result_data["post_refactoring"]["cumulative_tcc"] = 1.0

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
                n_methods = len(sg['methods']) if isinstance(sg['methods'], list) else sg['methods']
                logger.info(f"    {mark} {sg['name']} ({n_methods} methods)")
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
