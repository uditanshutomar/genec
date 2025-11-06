#!/usr/bin/env python3
"""Script to run GenEC pipeline on a single Java class."""

import argparse
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from genec.core.pipeline import GenECPipeline

# Temporary: load a hardcoded Anthropic API key (INSECURE — remove later)
try:
    # import here so the script still runs if the module isn't present
    from genec.utils.secrets import get_anthropic_api_key

    # set the environment variable for downstream consumers that read os.environ
    os.environ.setdefault("ANTHROPIC_API_KEY", get_anthropic_api_key())
except Exception:
    # If the secrets module isn't configured or raises, continue — the rest of
    # the pipeline may rely on other secret-loading strategies or environment.
    pass


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
        default=None,
        help='Maximum number of suggestions to generate (default: None = all valid clusters)'
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

    # Persist all suggestions (including failed ones) for debugging
    if result.suggestions:
        suggestion_dir = output_dir / result.class_name
        suggestion_dir.mkdir(parents=True, exist_ok=True)

        status_by_cluster = {
            verification.suggestion_id: verification.status
            for verification in result.verification_results
        }

        for idx, suggestion in enumerate(result.suggestions, 1):
            status = status_by_cluster.get(suggestion.cluster_id, "NOT_VERIFIED")
            prefix = f"{idx:02d}_{suggestion.proposed_class_name}_{status}"

            new_class_path = suggestion_dir / f"{prefix}_New.java"
            modified_path = suggestion_dir / f"{prefix}_Original.java"
            metadata_path = suggestion_dir / f"{prefix}_metadata.txt"

            with open(new_class_path, 'w', encoding='utf-8') as f:
                f.write(suggestion.new_class_code)

            with open(modified_path, 'w', encoding='utf-8') as f:
                f.write(suggestion.modified_original_code)

            with open(metadata_path, 'w', encoding='utf-8') as f:
                f.write(f"Proposed Class: {suggestion.proposed_class_name}\n")
                f.write(f"Status: {status}\n")
                f.write("Members:\n")
                for member in suggestion.cluster.member_names:
                    member_type = suggestion.cluster.member_types.get(member, 'unknown')
                    f.write(f"  - {member} ({member_type})\n")
                f.write("\nRationale:\n")
                f.write(suggestion.rationale.strip())
                f.write("\n")

            print(f"Saved suggestion #{idx} artifacts to {suggestion_dir}")

    # Save transformation guidance for rejected clusters
    rejected_clusters = [c for c in result.all_clusters if hasattr(c, 'rejection_issues') and hasattr(c, 'transformation_strategy') and c.transformation_strategy is not None]

    if rejected_clusters:
        transformations_dir = output_dir / "transformation_guidance"
        transformations_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*80}")
        print("TRANSFORMATION GUIDANCE FOR REJECTED CLUSTERS")
        print(f"{'='*80}\n")

        for idx, cluster in enumerate(rejected_clusters, 1):
            strategy = cluster.transformation_strategy

            print(f"\nCluster {cluster.id}: {strategy.pattern_name} pattern suggested (confidence: {strategy.confidence:.2f})")

            # Save detailed guidance to file
            guidance_file = transformations_dir / f"cluster_{cluster.id}_{strategy.pattern_name.replace(' ', '_')}.txt"

            with open(guidance_file, 'w', encoding='utf-8') as f:
                f.write(f"CLUSTER {cluster.id} - TRANSFORMATION GUIDANCE\n")
                f.write(f"{'='*80}\n\n")
                f.write(f"Pattern: {strategy.pattern_name}\n")
                f.write(f"Confidence: {strategy.confidence:.2f}\n\n")
                f.write(f"Description:\n{strategy.description}\n\n")
                f.write(f"Required Modifications:\n")
                for i, mod in enumerate(strategy.modifications_needed, 1):
                    f.write(f"  {i}. {mod}\n")

                if strategy.code_changes:
                    f.write(f"\nCode Structure:\n")
                    f.write(strategy.code_changes.get('transformation', ''))
                    f.write(f"\n")

                f.write(f"\nRejection Issues:\n")
                for issue in cluster.rejection_issues:
                    if issue.severity == 'error':
                        f.write(f"  - [{issue.severity.upper()}] {issue.issue_type}: {issue.description}\n")

            print(f"  Saved to: {guidance_file}")

        print(f"\nSaved {len(rejected_clusters)} transformation guidance files to {transformations_dir}")

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

    # Show applied refactorings at the end
    if result.applied_refactorings:
        successful_applications = [app for app in result.applied_refactorings if app.success]
        if successful_applications:
            print(f"\n{'='*80}")
            print("APPLIED REFACTORINGS")
            print(f"{'='*80}")
            print(f"\nSuccessfully applied {len(successful_applications)} refactoring(s):\n")

            for i, app in enumerate(successful_applications, 1):
                print(f"{i}. New class created:")
                print(f"   {app.new_class_path}")

            print(f"\nOriginal class modified:")
            print(f"   {app.original_class_path}")

            if app.backup_path:
                print(f"\nBackup saved to:")
                print(f"   {app.backup_path}")

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
