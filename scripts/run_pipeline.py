#!/usr/bin/env python3
"""Script to run GenEC pipeline on a single Java class."""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from genec.core.pipeline import GenECPipeline


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Run GenEC pipeline on a Java class'
    )

    parser.add_argument(
        '--class-file',
        required=True,
        help='Path to Java class file'
    )

    parser.add_argument(
        '--repo-path',
        required=True,
        help='Path to Git repository'
    )

    parser.add_argument(
        '--config',
        default='config/config.yaml',
        help='Path to configuration file (default: config/config.yaml)'
    )

    parser.add_argument(
        '--max-suggestions',
        type=int,
        default=5,
        help='Maximum number of suggestions to generate (default: 5)'
    )

    parser.add_argument(
        '--output-dir',
        default='data/outputs',
        help='Directory for output files (default: data/outputs)'
    )

    parser.add_argument(
        '--visualize',
        action='store_true',
        help='Generate graph visualizations'
    )

    args = parser.parse_args()

    # Initialize pipeline
    print(f"Initializing GenEC pipeline with config: {args.config}")
    pipeline = GenECPipeline(args.config)

    # Check prerequisites
    print("\nChecking prerequisites...")
    prereqs = pipeline.check_prerequisites()

    missing = [tool for tool, available in prereqs.items() if not available]
    if missing:
        print(f"Warning: Missing tools: {', '.join(missing)}")
        print("Some verification layers may be skipped.\n")

    # Run pipeline
    print(f"\nRunning GenEC on: {args.class_file}")
    print(f"Repository: {args.repo_path}\n")

    result = pipeline.run_full_pipeline(
        class_file=args.class_file,
        repo_path=args.repo_path,
        max_suggestions=args.max_suggestions
    )

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save verified suggestions
    print(f"\n{'='*80}")
    print("VERIFIED REFACTORING SUGGESTIONS")
    print(f"{'='*80}\n")

    if result.verified_suggestions:
        for i, suggestion in enumerate(result.verified_suggestions, 1):
            print(f"\n{'='*80}")
            print(f"Suggestion #{i}: {suggestion.proposed_class_name}")
            print(f"{'='*80}")
            print(f"\nRationale:\n{suggestion.rationale}\n")
            print(f"Members to extract:")
            for member in suggestion.cluster.member_names:
                member_type = suggestion.cluster.member_types.get(member, 'unknown')
                print(f"  - {member} ({member_type})")

            # Save code to files
            new_class_file = output_dir / f"{suggestion.proposed_class_name}.java"
            with open(new_class_file, 'w') as f:
                f.write(suggestion.new_class_code)
            print(f"\nNew class saved to: {new_class_file}")

            modified_file = output_dir / f"{result.class_name}_modified_{i}.java"
            with open(modified_file, 'w') as f:
                f.write(suggestion.modified_original_code)
            print(f"Modified class saved to: {modified_file}")

    else:
        print("No verified suggestions generated.")

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total clusters detected: {len(result.all_clusters)}")
    print(f"Filtered clusters: {len(result.filtered_clusters)}")
    print(f"Suggestions generated: {len(result.suggestions)}")
    print(f"Verified suggestions: {len(result.verified_suggestions)}")
    print(f"Execution time: {result.execution_time:.2f} seconds")

    # Metrics
    if result.original_metrics:
        print(f"\nOriginal Class Metrics:")
        for metric, value in result.original_metrics.items():
            print(f"  {metric}: {value:.3f}")

    # Visualize graphs if requested
    if args.visualize and result.filtered_clusters:
        print(f"\nGenerating graph visualizations...")
        # This would require re-running part of the pipeline to get the graphs
        # For now, just inform the user
        print("(Graph visualization not implemented in this script)")

    print(f"\n{'='*80}\n")

    return 0


if __name__ == '__main__':
    sys.exit(main())
