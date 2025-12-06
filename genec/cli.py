import argparse
import json
import logging
import os
import sys
from pathlib import Path

from genec.core.pipeline import GenECPipeline
from genec.utils.logging_utils import get_logger, setup_logger

logger = get_logger(__name__)

import signal

from dotenv import load_dotenv


def main():
    # Load .env file
    load_dotenv()

    # Track if we're in a cancellable state
    _cancellation_requested = False

    def handle_sigint(signum, frame):
        """Handle SIGINT (Ctrl+C) gracefully."""
        nonlocal _cancellation_requested
        if _cancellation_requested:
            # Second Ctrl+C, force exit
            sys.exit(130)
        _cancellation_requested = True
        raise KeyboardInterrupt("Cancellation requested")

    # Install signal handler (allow graceful cancellation)
    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    parser = argparse.ArgumentParser(description="GenEC: Generative Extract Class Refactoring Tool")
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

    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"

    # If JSON output is requested, ensure logs go to stderr so they don't corrupt stdout
    if args.json:
        # Configure root logger to write to stderr
        logging.basicConfig(stream=sys.stderr, level=getattr(logging, log_level))
        # Also setup our custom logger
        setup_logger("genec", level=log_level)
        # Ensure our custom logger's handlers are also stderr
        logger = logging.getLogger("genec")
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.stream = sys.stderr
    else:
        setup_logger("genec", level=log_level)
        logger = logging.getLogger("genec")

    # Setup API key
    if args.api_key:
        os.environ["ANTHROPIC_API_KEY"] = args.api_key

    # Verify API key is available (either from args, env, or .env)
    from genec.utils.secrets import get_anthropic_api_key

    if not get_anthropic_api_key():
        logger.warning(
            "No API key found (checked args, env, and .env). LLM features will be disabled."
        )

    # Validate paths
    target_path = Path(args.target).resolve()
    repo_path = Path(args.repo).resolve()
    config_path = Path(args.config).resolve()

    if not target_path.exists():
        logger.error(f"Target file not found: {target_path}")
        sys.exit(1)

    if not repo_path.exists():
        logger.error(f"Repository path not found: {repo_path}")
        sys.exit(1)

    # Construct config overrides
    config_overrides = {}

    if args.apply_all:
        config_overrides["refactoring_application"] = {
            "enabled": True,
            "auto_apply": True,
            "dry_run": False,
        }

    # Pass coverage check flag to verification config
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

    if args.no_build:
        config_overrides["auto_build_dependencies"] = False

    # Initialize pipeline
    try:
        pipeline = GenECPipeline(
            config_file=str(config_path) if config_path.exists() else None,
            config_overrides=config_overrides,
        )

        if not args.json:
            logger.info(f"Running GenEC on {target_path}...")

        # Start WebSocket progress server if requested
        progress_server = None
        if args.websocket:
            try:
                from genec.utils.progress_server import get_progress_server

                progress_server = get_progress_server(args.websocket)
                progress_server.start()
                logger.info(f"WebSocket progress server started on port {args.websocket}")
            except Exception as e:
                logger.warning(f"Failed to start WebSocket server: {e}")

        import time

        start_time = time.time()

        results = pipeline.run_full_pipeline(
            class_file=str(target_path),
            repo_path=str(repo_path),
            max_suggestions=args.max_suggestions,
        )

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

        # Calculate and log total runtime
        total_runtime = time.time() - start_time
        runtime_str = f"{total_runtime:.1f}s" if total_runtime < 60 else f"{total_runtime/60:.1f}m"

        if args.json:
            # Build message explaining results
            if not results.suggestions:
                message = "No refactoring suggestions found. Possible reasons: class is already well-factored, no cohesive method clusters detected, or class is too small."
            elif not results.verified_suggestions:
                message = f"Generated {len(results.suggestions)} suggestions but none passed verification. Check verification logs for details."
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
            }
            print(json.dumps(output, indent=2))
        else:
            # Dry-run mode: show detailed summary of what WOULD be applied
            if args.dry_run and results.verified_suggestions:
                print("\n" + "=" * 60)
                print("DRY-RUN SUMMARY - No changes will be made")
                print("=" * 60)
                print(f"\nFile: {target_path.name}")
                print(f"Total verified suggestions: {len(results.verified_suggestions)}")
                print("\nChanges that WOULD be applied:\n")

                for i, s in enumerate(results.verified_suggestions, 1):
                    methods = s.methods if hasattr(s, "methods") else []
                    method_count = len(methods) if methods else "unknown"

                    confidence_str = f" (confidence: {s.confidence_score:.2f})" if s.confidence_score is not None else ""
                    print(f"  {i}. Extract class: {s.proposed_class_name}{confidence_str}")
                    print(f"     Methods to move: {method_count}")
                    if methods:
                        for m in methods[:5]:  # Show first 5 methods
                            print(f"       - {m}")
                        if len(methods) > 5:
                            print(f"       ... and {len(methods) - 5} more")
                    if hasattr(s, "reasoning") and s.reasoning:
                        print(f"     Reason: {s.reasoning[:100]}...")
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

            # Show confidence metrics if available
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
            logger.error(f"Error running pipeline: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup generated.java if it exists
        generated_file = target_path.parent / "generated.java"
        if generated_file.exists():
            try:
                generated_file.unlink()
                if not args.json:
                    logger.info(f"Cleaned up artifact: {generated_file}")
            except Exception as e:
                if not args.json:
                    logger.warning(f"Failed to cleanup artifact {generated_file}: {e}")


if __name__ == "__main__":
    main()
