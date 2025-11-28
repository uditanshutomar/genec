import argparse
import json
import os
import sys
from pathlib import Path

from genec.core.pipeline import GenECPipeline
from genec.utils.logging_utils import get_logger, setup_logger

logger = get_logger(__name__)

def main():
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
    
    args = parser.parse_args()

    # Setup logging
    log_level = 'DEBUG' if args.verbose else 'INFO'
    setup_logger('genec', level=log_level)
    
    # Setup API key
    if args.api_key:
        os.environ["ANTHROPIC_API_KEY"] = args.api_key
    elif "ANTHROPIC_API_KEY" not in os.environ:
        # Try to load from secrets util if available
        try:
            from genec.utils.secrets import get_anthropic_api_key
            os.environ["ANTHROPIC_API_KEY"] = get_anthropic_api_key()
        except Exception:
            logger.warning("No API key provided. LLM features will be disabled.")

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
        
    # Initialize pipeline
    try:
        pipeline = GenECPipeline(str(config_path) if config_path.exists() else None)
        
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
                        "verified": s in results.verified_suggestions
                    } for s in results.suggestions
                ]
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
