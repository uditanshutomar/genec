#!/usr/bin/env python3
"""Script to evaluate GenEC and baselines against ground truth."""

import argparse
import sys
import json
from pathlib import Path
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from genec.core.pipeline import GenECPipeline
from genec.baselines.bavota_baseline import BavotaBaseline
from genec.baselines.naive_llm_baseline import NaiveLLMBaseline
from genec.evaluation.ground_truth_builder import GroundTruthBuilder
from genec.evaluation.comparator import Comparator


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Evaluate GenEC and baselines against ground truth'
    )

    parser.add_argument(
        '--ground-truth',
        required=True,
        help='Path to ground truth JSON file'
    )

    parser.add_argument(
        '--repo-path',
        required=True,
        help='Path to Git repository'
    )

    parser.add_argument(
        '--config',
        default='config/config.yaml',
        help='Path to configuration file'
    )

    parser.add_argument(
        '--output',
        default='data/outputs/evaluation.json',
        help='Output file for evaluation results'
    )

    parser.add_argument(
        '--approaches',
        nargs='+',
        default=['genec', 'bavota', 'naive_llm'],
        choices=['genec', 'bavota', 'naive_llm'],
        help='Approaches to evaluate'
    )

    parser.add_argument(
        '--max-classes',
        type=int,
        default=None,
        help='Maximum number of classes to evaluate'
    )

    args = parser.parse_args()

    # Load ground truth
    print(f"Loading ground truth from: {args.ground_truth}")
    gt_builder = GroundTruthBuilder()
    ground_truth = gt_builder.load_ground_truth(args.ground_truth)

    if not ground_truth:
        print("Error: No ground truth refactorings found")
        return 1

    print(f"Loaded {len(ground_truth)} ground truth refactorings")

    # Get unique source classes
    source_classes = list(set([gt.source_class for gt in ground_truth]))

    if args.max_classes:
        source_classes = source_classes[:args.max_classes]

    print(f"Evaluating on {len(source_classes)} classes")

    # Initialize approaches
    approaches = {}

    if 'genec' in args.approaches:
        print("\nInitializing GenEC...")
        approaches['GenEC'] = GenECPipeline(args.config)

    if 'bavota' in args.approaches:
        print("Initializing Bavota baseline...")
        approaches['Bavota'] = BavotaBaseline()

    if 'naive_llm' in args.approaches:
        print("Initializing Naive LLM baseline...")
        try:
            approaches['NaiveLLM'] = NaiveLLMBaseline()
        except ValueError as e:
            print(f"Warning: Could not initialize Naive LLM baseline: {e}")

    # Run evaluation
    comparator = Comparator()
    all_results = {name: [] for name in approaches.keys()}

    for i, source_class in enumerate(source_classes, 1):
        print(f"\n{'='*80}")
        print(f"[{i}/{len(source_classes)}] Evaluating: {source_class}")
        print(f"{'='*80}")

        # Find class file in repository
        class_file = find_class_file(args.repo_path, source_class)

        if not class_file:
            print(f"Warning: Could not find class file for {source_class}")
            continue

        # Run each approach
        for approach_name, approach in approaches.items():
            print(f"\nRunning {approach_name}...")

            try:
                if approach_name == 'GenEC':
                    result = approach.run_full_pipeline(class_file, args.repo_path)
                    suggestions = result.verified_suggestions

                elif approach_name == 'Bavota':
                    suggestions = approach.run(class_file)

                elif approach_name == 'NaiveLLM':
                    suggestions = approach.run(class_file)

                all_results[approach_name].append({
                    'class': source_class,
                    'suggestions': suggestions
                })

                print(f"  Generated {len(suggestions)} suggestions")

            except Exception as e:
                print(f"  Error: {e}")
                all_results[approach_name].append({
                    'class': source_class,
                    'suggestions': []
                })

    # Calculate metrics for each approach
    print(f"\n{'='*80}")
    print("CALCULATING METRICS")
    print(f"{'='*80}\n")

    comparison_results = []

    for approach_name, results in all_results.items():
        print(f"Evaluating {approach_name}...")

        # Aggregate suggestions
        all_suggestions = []
        for result in results:
            all_suggestions.extend(result['suggestions'])

        # Evaluate
        metrics = comparator.evaluate_suggestions(
            all_suggestions,
            ground_truth,
            source_class=""  # Evaluate across all classes
        )

        from genec.evaluation.comparator import ComparisonResult
        comparison = ComparisonResult(
            tool_name=approach_name,
            metrics=metrics
        )

        comparison_results.append(comparison)

    # Generate summary table
    print(f"\n{comparator.generate_summary_table(comparison_results)}")

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    comparator.save_evaluation_report(comparison_results, args.output)

    print(f"\nEvaluation results saved to: {args.output}")

    return 0


def find_class_file(repo_path: str, class_name: str) -> str:
    """
    Find Java class file in repository.

    Args:
        repo_path: Path to repository
        class_name: Fully qualified class name

    Returns:
        Path to class file or None
    """
    # Extract simple class name
    simple_name = class_name.split('.')[-1]

    # Search for file
    repo = Path(repo_path)
    matches = list(repo.rglob(f"{simple_name}.java"))

    if matches:
        return str(matches[0])

    return None


if __name__ == '__main__':
    sys.exit(main())
