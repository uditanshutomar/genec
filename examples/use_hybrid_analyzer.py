#!/usr/bin/env python3
"""
Example: Using HybridDependencyAnalyzer

This example shows how to use the hybrid analyzer that automatically
tries Spoon first and falls back to JavaParser if Spoon fails.
"""

import sys
from pathlib import Path

# Add genec to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from genec.core.hybrid_dependency_analyzer import HybridDependencyAnalyzer


def main():
    """Demonstrate hybrid analyzer usage."""

    print("=" * 80)
    print("HYBRID DEPENDENCY ANALYZER DEMO")
    print("=" * 80)
    print()

    # Create hybrid analyzer
    # It will automatically detect if Spoon is available
    analyzer = HybridDependencyAnalyzer(
        prefer_spoon=True  # Try Spoon first if available
    )

    # Example Java files to analyze
    test_files = [
        "/tmp/ComprehensiveValidation.java",
        "/tmp/RealWorldTest.java",
    ]

    results = []
    for java_file in test_files:
        if not Path(java_file).exists():
            print(f"⚠️  Skipping {java_file} (not found)")
            continue

        print(f"\n{'=' * 80}")
        print(f"Analyzing: {java_file}")
        print(f"{'=' * 80}")

        try:
            result = analyzer.analyze_class(java_file)

            if result:
                results.append((java_file, result))
                print(f"✓ Success: {result.class_name}")
                print(f"  Methods: {len(result.methods)}")
                print(f"  Constructors: {len(result.constructors)}")
                print(f"  Fields: {len(result.fields)}")
                print(f"  Dependency matrix: {result.dependency_matrix.shape}")
            else:
                print(f"✗ Failed to analyze {java_file}")

        except Exception as e:
            print(f"✗ Error analyzing {java_file}: {e}")

    # Print metrics summary
    print("\n" + "=" * 80)
    print("ANALYSIS SUMMARY")
    print("=" * 80)
    analyzer.print_metrics()

    # Show which parser was used more
    if analyzer.metrics.spoon_successes > 0:
        print("✓ Spoon was used successfully")
    if analyzer.metrics.fallback_successes > 0:
        print("✓ JavaParser fallback was used")

    print(f"\nTotal files analyzed: {len(results)}")

    return results


if __name__ == "__main__":
    main()
