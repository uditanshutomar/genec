import argparse
import json
import logging
import os
import sys
from pathlib import Path

from genec.core.pipeline import GenECPipeline
from genec.utils.logging_utils import get_logger, setup_logger

logger = get_logger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create and return the argument parser."""
    parser = argparse.ArgumentParser(
        description="GenEC: Generative Extract Class Refactoring Tool"
    )
    parser.add_argument("--version", action="version", version="GenEC 1.0.0")
    parser.add_argument("--target", required=True, help="Path to the Java class file to refactor")
    parser.add_argument("--repo", required=True, help="Path to the repository root")
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to configuration file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--multi-file",
        action="store_true",
        help="Enable multi-file mode: analyze dependency order across files",
    )
    parser.add_argument("--api-key", help="Anthropic API key (overrides ANTHROPIC_API_KEY env var)")
    parser.add_argument(
        "--max-suggestions",
        type=int,
        default=5,
        help="Maximum number of suggestions to generate (default: 5)",
    )
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose logging (DEBUG level)"
    )
    parser.add_argument(
        "--apply-all", action="store_true", help="Automatically apply all verified refactorings"
    )
    parser.add_argument("--min-cluster-size", type=int, help="Minimum cluster size")
    parser.add_argument("--max-cluster-size", type=int, help="Maximum cluster size")
    parser.add_argument("--min-cohesion", type=float, help="Minimum cohesion threshold")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what WOULD be applied without making changes"
    )
    parser.add_argument(
        "--check-coverage",
        action="store_true",
        help="Verify that extracted classes are covered by tests (requires JaCoCo)",
    )
    parser.add_argument(
        "--websocket",
        type=int,
        metavar="PORT",
        help="Enable WebSocket progress server on specified port (e.g., 9876)",
    )
    parser.add_argument(
        "--no-build", action="store_true", help="Disable automatic building of dependencies"
    )
    parser.add_argument(
        "--report-dir",
        help="Directory to save pipeline reports (default: .genec/reports in repo)",
    )
    parser.add_argument(
        "--cache-dir",
        help="Directory for LLM response cache (reproducibility)",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Use cached LLM responses if available",
    )
    return parser


def validate_target_file(file_path: str) -> Path:
    """
    Validate that the target file exists and is a Java file.

    Args:
        file_path: Path to the target file

    Returns:
        Resolved Path object

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is not a .java file
    """
    path = Path(file_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Target file not found: {path}")

    if path.suffix.lower() != ".java":
        raise ValueError(f"Target must be a .java file, got: {path.suffix}")

    return path


def validate_api_key_for_llm_features() -> bool:
    """
    Validate that an API key is available for LLM features.

    Returns:
        True if API key is available, False otherwise
    """
    from genec.utils.secrets import get_anthropic_api_key

    api_key = get_anthropic_api_key()
    if not api_key:
        return False

    # Basic format validation (Anthropic keys start with sk-ant-)
    if not api_key.startswith("sk-ant-"):
        logger.warning("API key does not appear to be a valid Anthropic key (should start with sk-ant-)")
        return False

    return True

import signal
import time

from dotenv import load_dotenv


def _setup_logging(args) -> logging.Logger:
    """Configure logging based on CLI arguments.

    Returns the configured logger instance.
    """
    log_level = "DEBUG" if args.verbose else "INFO"

    if args.json:
        # Ensure logs go to stderr so they don't corrupt stdout JSON
        logging.basicConfig(stream=sys.stderr, level=getattr(logging, log_level))
        setup_logger("genec", level=log_level)
        _logger = logging.getLogger("genec")
        for handler in _logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.stream = sys.stderr
    else:
        setup_logger("genec", level=log_level)
        _logger = logging.getLogger("genec")

    return _logger


def _validate_inputs(args) -> tuple[Path, Path, Path]:
    """Validate target file, repo path, and config path.

    Returns:
        (target_path, repo_path, config_path) as resolved Path objects.

    Raises:
        SystemExit on validation failure (prints JSON or logs error first).
    """
    _logger = logging.getLogger("genec")

    # Setup API key
    if args.api_key:
        os.environ["ANTHROPIC_API_KEY"] = args.api_key

    if not validate_api_key_for_llm_features():
        _logger.warning(
            "No valid API key found (checked args, env, and .env). "
            "LLM-based naming and validation will be disabled. "
            "Set ANTHROPIC_API_KEY environment variable or pass --api-key."
        )

    # Validate target file
    try:
        target_path = validate_target_file(args.target)
    except (FileNotFoundError, ValueError) as e:
        error_msg = str(e)
        if args.json:
            print(json.dumps({"status": "error", "error": error_msg}))
        else:
            _logger.error(error_msg)
        sys.exit(1)

    # Validate repository path
    repo_path = Path(args.repo).resolve()
    config_path = Path(args.config).resolve()

    if not repo_path.exists():
        error_msg = f"Repository path not found: {repo_path}"
        if args.json:
            print(json.dumps({"status": "error", "error": error_msg}))
        else:
            _logger.error(error_msg)
        sys.exit(1)

    return target_path, repo_path, config_path


def _build_config_overrides(args) -> dict:
    """Build pipeline config overrides from CLI arguments."""
    config_overrides = {}

    if args.apply_all:
        config_overrides["refactoring_application"] = {
            "enabled": True,
            "auto_apply": True,
            "dry_run": False,
        }

    if args.check_coverage:
        if "verification" not in config_overrides:
            config_overrides["verification"] = {}
        config_overrides["verification"]["enable_coverage"] = True

    if (
        args.min_cluster_size is not None
        or args.max_cluster_size is not None
        or args.min_cohesion is not None
    ):
        clustering_overrides = {}
        if args.min_cluster_size is not None:
            clustering_overrides["min_cluster_size"] = args.min_cluster_size
        if args.max_cluster_size is not None:
            clustering_overrides["max_cluster_size"] = args.max_cluster_size
        if args.min_cohesion is not None:
            clustering_overrides["min_cohesion"] = args.min_cohesion
        config_overrides["clustering"] = clustering_overrides

    if args.dry_run:
        if "refactoring_application" not in config_overrides:
            config_overrides["refactoring_application"] = {}
        config_overrides["refactoring_application"]["dry_run"] = True

    if args.no_build:
        config_overrides["auto_build_dependencies"] = False

    if args.cache_dir or args.use_cache:
        if "llm" not in config_overrides:
            config_overrides["llm"] = {}
        if args.cache_dir:
            config_overrides["llm"]["cache_dir"] = args.cache_dir
        if args.use_cache:
            config_overrides["llm"]["use_cache"] = True

    return config_overrides


def _run_pipeline(args, target_path: Path, repo_path: Path, config_path: Path, config_overrides: dict):
    """Execute the GenEC pipeline and return (results, runtime_str).

    Also handles WebSocket server lifecycle and report saving.
    """
    _logger = logging.getLogger("genec")

    pipeline = GenECPipeline(
        config_file=str(config_path) if config_path.exists() else None,
        config_overrides=config_overrides,
    )

    if not args.json:
        _logger.info(f"Running GenEC on {target_path}...")

    # Start WebSocket progress server if requested
    progress_server = None
    if args.websocket:
        try:
            from genec.utils.progress_server import get_progress_server

            progress_server = get_progress_server(args.websocket)
            progress_server.start()
            _logger.info(f"WebSocket progress server started on port {args.websocket}")
        except Exception as e:
            _logger.warning(f"Failed to start WebSocket server: {e}")

    start_time = time.time()

    results = pipeline.run_full_pipeline(
        class_file=str(target_path),
        repo_path=str(repo_path),
        max_suggestions=args.max_suggestions,
    )

    # Save report to custom directory if specified
    if args.report_dir:
        report_dir = Path(args.report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{Path(args.target).stem}_report.json"
        report_path.write_text(json.dumps(results.pipeline_report, indent=2, default=str))
        _logger.info(f"Pipeline report saved to {report_path}")

    # Stop WebSocket server
    if progress_server:
        progress_server.emit_complete(
            {
                "suggestions": (
                    len(results.verified_suggestions) if results.verified_suggestions else 0
                )
            }
        )
        progress_server.stop()

    total_runtime = time.time() - start_time
    runtime_str = f"{total_runtime:.1f}s" if total_runtime < 60 else f"{total_runtime/60:.1f}m"

    return results, runtime_str


def _format_json_output(results, runtime_str: str) -> str:
    """Format pipeline results as a JSON string for machine consumption."""
    if not results.suggestions:
        message = (
            "No refactoring suggestions found. Possible reasons: class is already "
            "well-factored, no cohesive method clusters detected, or class is too small."
        )
    elif not results.verified_suggestions:
        message = (
            f"Generated {len(results.suggestions)} suggestions but none passed "
            "verification. Check verification logs for details."
        )
    else:
        message = f"Successfully generated {len(results.verified_suggestions)} verified suggestions."

    output = {
        "status": "success",
        "message": message,
        "runtime": runtime_str,
        "original_metrics": results.original_metrics,
        "suggestions": [
            {
                "name": s.proposed_class_name,
                "verified": s in results.verified_suggestions,
                "new_class_code": s.new_class_code or "",
                "modified_original_code": s.modified_original_code or "",
                "rationale": getattr(s, "rationale", None),
                "reasoning": getattr(s, "reasoning", None),
                "confidence_score": getattr(s, "confidence_score", None),
                "quality_score": (
                    s.cluster.quality_score if getattr(s, "cluster", None) else getattr(s, "quality_score", None)
                ),
                "quality_tier": (
                    s.cluster.quality_tier.value
                    if getattr(s, "cluster", None) and s.cluster.quality_tier
                    else getattr(s, "quality_tier", None)
                ),
                "quality_reasons": (
                    s.cluster.quality_reasons if getattr(s, "cluster", None) else getattr(s, "quality_reasons", None)
                ),
                "verification_status": getattr(s, "verification_status", None),
                "methods": s.cluster.get_methods() if getattr(s, "cluster", None) else None,
                "fields": s.cluster.get_fields() if getattr(s, "cluster", None) else None,
            }
            for s in results.suggestions
        ],
        "applied_refactorings": [
            {
                "success": r.success,
                "new_class_path": r.new_class_path,
                "original_class_path": r.original_class_path,
                "error_message": r.error_message,
                "commit_hash": r.commit_hash,
            }
            for r in results.applied_refactorings
        ],
        "graph_data": results.graph_data,
        "clusters": [
            {
                "name": f"Cluster_{i}",
                "members": c.member_names,
                "quality_tier": c.quality_tier.value if c.quality_tier else 'potential',
                "cohesion_score": getattr(c, 'internal_cohesion', 0),
            }
            for i, c in enumerate(results.ranked_clusters)
        ],
    }
    return json.dumps(output, indent=2)


def _format_text_output(results, runtime_str: str, args, target_path: Path) -> None:
    """Print human-readable pipeline results to stdout."""
    # Dry-run mode: show detailed summary of what WOULD be applied
    if args.dry_run and results.verified_suggestions:
        print("\n" + "=" * 60)
        print("DRY-RUN SUMMARY - No changes will be made")
        print("=" * 60)
        print(f"\nFile: {target_path.name}")
        print(f"Total verified suggestions: {len(results.verified_suggestions)}")
        print("\nChanges that WOULD be applied:\n")

        for i, s in enumerate(results.verified_suggestions, 1):
            methods = s.cluster.get_methods() if hasattr(s, 'cluster') and s.cluster else []
            method_count = len(methods) if methods else "unknown"

            confidence_str = f" (confidence: {s.confidence_score:.2f})" if s.confidence_score is not None else ""
            print(f"  {i}. Extract class: {s.proposed_class_name}{confidence_str}")
            print(f"     Methods to move: {method_count}")
            if methods:
                for m in methods[:5]:
                    print(f"       - {m}")
                if len(methods) > 5:
                    print(f"       ... and {len(methods) - 5} more")
            reasoning = getattr(s, "reasoning", None)
            if reasoning:
                print(f"     Reason: {reasoning[:100]}...")
            print()

        print("-" * 60)
        print("To apply these changes, run without --dry-run flag")
        print("=" * 60)

    print("\n" + "=" * 50)
    print(f"Refactoring Completed Successfully (Runtime: {runtime_str})")
    print("=" * 50)
    print(f"Original Metrics: {results.original_metrics}")
    print(f"Suggestions Generated: {len(results.suggestions)}")
    print(f"Verified Suggestions: {len(results.verified_suggestions)}")

    if results.avg_confidence > 0:
        print(f"Confidence Metrics: avg={results.avg_confidence:.2f}, "
              f"min={results.min_confidence:.2f}, max={results.max_confidence:.2f}, "
              f"high(>=0.8)={results.high_confidence_count}")

    print(f"Total Runtime: {runtime_str}")

    if results.verified_suggestions:
        print("\nVerified Suggestions:")
        for i, s in enumerate(results.verified_suggestions, 1):
            confidence_str = f" (confidence: {s.confidence_score:.2f})" if s.confidence_score is not None else ""
            print(f"{i}. {s.proposed_class_name}{confidence_str}")


def main():
    load_dotenv()

    # Install signal handlers for graceful cancellation
    _cancellation_requested = False

    def handle_sigint(signum, frame):
        nonlocal _cancellation_requested
        if _cancellation_requested:
            sys.exit(130)
        _cancellation_requested = True
        raise KeyboardInterrupt("Cancellation requested")

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    args = create_parser().parse_args()
    _logger = _setup_logging(args)
    target_path, repo_path, config_path = _validate_inputs(args)
    config_overrides = _build_config_overrides(args)

    try:
        results, runtime_str = _run_pipeline(args, target_path, repo_path, config_path, config_overrides)

        if args.json:
            print(_format_json_output(results, runtime_str))
        else:
            _format_text_output(results, runtime_str, args, target_path)

    except KeyboardInterrupt:
        if args.json:
            print(json.dumps({"status": "cancelled", "error": "Operation cancelled by user"}))
        else:
            print("\nOperation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        if args.json:
            print(json.dumps({"status": "error", "error": str(e)}))
        else:
            _logger.error(f"Error running pipeline: {e}", exc_info=True)
        sys.exit(1)
    finally:
        generated_file = target_path.parent / "generated.java"
        if generated_file.exists():
            try:
                generated_file.unlink()
                if not args.json:
                    _logger.info(f"Cleaned up artifact: {generated_file}")
            except Exception as e:
                if not args.json:
                    _logger.warning(f"Failed to cleanup artifact {generated_file}: {e}")


if __name__ == "__main__":
    main()
