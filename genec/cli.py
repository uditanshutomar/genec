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

    # Ignore SIGINT to debug mysterious KeyboardInterrupt
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    parser = argparse.ArgumentParser(description="GenEC: Generative Extract Class Refactoring Tool")
    
    parser.add_argument(
        "--target", 
        required=True, 
        help="Path to the Java class file to refactor"
    )
    parser.add_argument(
        "--repo", 
        required=True, 
        help="Path to the repository root"
    )
    parser.add_argument(
        "--config", 
        default="config/config.yaml", 
        help="Path to configuration file (default: config/config.yaml)"
    )
    parser.add_argument(
        "--api-key", 
        help="Anthropic API key (overrides ANTHROPIC_API_KEY env var)"
    )
    parser.add_argument(
        "--max-suggestions",
        type=int,
        default=5,
        help="Maximum number of suggestions to generate (default: 5)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level)"
    )
    parser.add_argument(
        "--apply-all",
        action="store_true",
        help="Automatically apply all verified refactorings"
    )
    parser.add_argument(
        "--min-cluster-size",
        type=int,
        help="Minimum cluster size"
    )
    parser.add_argument(
        "--max-cluster-size",
        type=int,
        help="Maximum cluster size"
    )
    parser.add_argument(
        "--min-cohesion",
        type=float,
        help="Minimum cohesion threshold"
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Disable automatic building of dependencies"
    )
    
    args = parser.parse_args()

    # Setup logging
    log_level = 'DEBUG' if args.verbose else 'INFO'
    
    # If JSON output is requested, ensure logs go to stderr so they don't corrupt stdout
    if args.json:
        # Configure root logger to write to stderr
        logging.basicConfig(stream=sys.stderr, level=getattr(logging, log_level))
        # Also setup our custom logger
        setup_logger('genec', level=log_level)
        # Ensure our custom logger's handlers are also stderr
        logger = logging.getLogger('genec')
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.stream = sys.stderr
    else:
        setup_logger('genec', level=log_level)
        logger = logging.getLogger('genec')
    
    # Setup API key
    if args.api_key:
        os.environ["ANTHROPIC_API_KEY"] = args.api_key
    
    # Verify API key is available (either from args, env, or .env)
    from genec.utils.secrets import get_anthropic_api_key
    if not get_anthropic_api_key():
        logger.warning("No API key found (checked args, env, and .env). LLM features will be disabled.")

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
            "dry_run": False
        }
        
    if args.min_cluster_size is not None or args.max_cluster_size is not None or args.min_cohesion is not None:
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
            config_overrides=config_overrides
        )
        
        if not args.json:
            logger.info(f"Running GenEC on {target_path}...")
        
        results = pipeline.run_full_pipeline(
            class_file=str(target_path),
            repo_path=str(repo_path),
            max_suggestions=args.max_suggestions
        )
        
        if args.json:
            output = {
                "status": "success",
                "original_metrics": results.original_metrics,
                "suggestions": [
                    {
                        "name": s.proposed_class_name,
                        "verified": s in results.verified_suggestions,
                        "new_class_code": s.new_class_code or "",
                        "modified_original_code": s.modified_original_code or ""
                    } for s in results.suggestions
                ],
                "applied_refactorings": [
                    {
                        "success": r.success,
                        "new_class_path": r.new_class_path,
                        "original_class_path": r.original_class_path,
                        "error_message": r.error_message,
                        "commit_hash": r.commit_hash
                    } for r in results.applied_refactorings
                ],
                "graph_data": results.graph_data
            }
            print(json.dumps(output, indent=2))
        else:
            print("\n" + "="*50)
            print("Refactoring Completed Successfully")
            print("="*50)
            print(f"Original Metrics: {results.original_metrics}")
            print(f"Suggestions Generated: {len(results.suggestions)}")
            print(f"Verified Suggestions: {len(results.verified_suggestions)}")
            
            if results.verified_suggestions:
                print("\nVerified Suggestions:")
                for i, s in enumerate(results.verified_suggestions, 1):
                    print(f"{i}. {s.proposed_class_name}")
                
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
