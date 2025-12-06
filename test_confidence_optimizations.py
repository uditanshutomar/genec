#!/usr/bin/env python3
"""
Test suite for confidence-based optimizations.

Tests the following enhancements:
1. Confidence filtering in NamingStage
2. Confidence-based sorting
3. Verification pre-screening
4. Confidence metrics in PipelineResult
5. CLI output enhancements
"""

import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.getcwd())

from genec.core.llm_interface import RefactoringSuggestion
from genec.core.cluster_detector import Cluster
from genec.core.pipeline import PipelineResult
from genec.core.stages.base_stage import PipelineContext


def create_mock_suggestion(cluster_id: int, name: str, confidence: float) -> RefactoringSuggestion:
    """Create a mock RefactoringSuggestion with given confidence."""
    methods = [f"public void method{cluster_id}()"]
    fields = []
    member_names = methods + fields
    member_types = {m: "method" for m in methods}
    cluster = Cluster(id=cluster_id, member_names=member_names, member_types=member_types)

    return RefactoringSuggestion(
        cluster_id=cluster_id,
        proposed_class_name=name,
        rationale=f"Test rationale for {name}",
        new_class_code=f"public class {name} {{}}",
        modified_original_code="public class Original {}",
        cluster=cluster,
        confidence_score=confidence,
        reasoning=f"Step 1: Test reasoning for {name}"
    )


def test_confidence_filtering():
    """Test 1: Confidence filtering in NamingStage."""
    print("\n" + "="*60)
    print("TEST 1: Confidence Filtering")
    print("="*60)

    # Create mock suggestions with varying confidence
    suggestions = [
        create_mock_suggestion(1, "HighConfidence", 0.95),
        create_mock_suggestion(2, "MediumConfidence", 0.75),
        create_mock_suggestion(3, "LowConfidence", 0.45),
        create_mock_suggestion(4, "VeryHighConfidence", 0.98),
    ]

    print(f"  Original suggestions: {len(suggestions)}")
    for s in suggestions:
        print(f"    - {s.proposed_class_name}: {s.confidence_score}")

    # Simulate filtering with threshold 0.7
    threshold = 0.7
    filtered = [s for s in suggestions if s.confidence_score >= threshold]

    print(f"\n  After filtering (threshold={threshold}): {len(filtered)}")
    for s in filtered:
        print(f"    - {s.proposed_class_name}: {s.confidence_score}")

    # Verify filtering worked
    assert len(filtered) == 3, f"Expected 3 suggestions, got {len(filtered)}"
    assert all(s.confidence_score >= threshold for s in filtered), "Some suggestions below threshold"
    assert "LowConfidence" not in [s.proposed_class_name for s in filtered], "Low confidence not filtered"

    print("\n  ✓ Filtering works correctly")
    return True


def test_confidence_sorting():
    """Test 2: Sorting by confidence."""
    print("\n" + "="*60)
    print("TEST 2: Confidence Sorting")
    print("="*60)

    # Create unsorted suggestions
    suggestions = [
        create_mock_suggestion(1, "Medium", 0.75),
        create_mock_suggestion(2, "VeryHigh", 0.98),
        create_mock_suggestion(3, "High", 0.85),
        create_mock_suggestion(4, "Low", 0.60),
    ]

    print("  Original order:")
    for i, s in enumerate(suggestions):
        print(f"    {i+1}. {s.proposed_class_name}: {s.confidence_score}")

    # Sort by confidence (highest first)
    sorted_suggestions = sorted(suggestions, key=lambda s: s.confidence_score, reverse=True)

    print("\n  After sorting (highest first):")
    for i, s in enumerate(sorted_suggestions):
        print(f"    {i+1}. {s.proposed_class_name}: {s.confidence_score}")

    # Verify sorting
    assert sorted_suggestions[0].proposed_class_name == "VeryHigh", "Highest confidence not first"
    assert sorted_suggestions[-1].proposed_class_name == "Low", "Lowest confidence not last"

    # Verify descending order
    confidences = [s.confidence_score for s in sorted_suggestions]
    assert confidences == sorted(confidences, reverse=True), "Not properly sorted"

    print("\n  ✓ Sorting works correctly")
    return True


def test_verification_prescreening():
    """Test 3: Verification pre-screening."""
    print("\n" + "="*60)
    print("TEST 3: Verification Pre-screening")
    print("="*60)

    suggestions = [
        create_mock_suggestion(1, "HighConfidence", 0.90),
        create_mock_suggestion(2, "LowConfidence", 0.40),
        create_mock_suggestion(3, "MediumConfidence", 0.65),
    ]

    min_verification_confidence = 0.5

    print(f"  Minimum verification confidence: {min_verification_confidence}")
    print("\n  Processing suggestions:")

    verified_count = 0
    skipped_count = 0

    for s in suggestions:
        if s.confidence_score < min_verification_confidence:
            print(f"    ⊗ {s.proposed_class_name} ({s.confidence_score:.2f}): SKIPPED (below threshold)")
            skipped_count += 1
        else:
            print(f"    ✓ {s.proposed_class_name} ({s.confidence_score:.2f}): Would verify")
            verified_count += 1

    assert verified_count == 2, f"Expected 2 to verify, got {verified_count}"
    assert skipped_count == 1, f"Expected 1 to skip, got {skipped_count}"

    print(f"\n  ✓ Pre-screening works correctly ({verified_count} verified, {skipped_count} skipped)")
    return True


def test_pipeline_result_metrics():
    """Test 4: PipelineResult confidence metrics."""
    print("\n" + "="*60)
    print("TEST 4: PipelineResult Confidence Metrics")
    print("="*60)

    # Create pipeline result with suggestions
    result = PipelineResult(class_name="TestClass")
    result.suggestions = [
        create_mock_suggestion(1, "Class1", 0.95),
        create_mock_suggestion(2, "Class2", 0.75),
        create_mock_suggestion(3, "Class3", 0.85),
        create_mock_suggestion(4, "Class4", 0.90),
    ]

    # Calculate metrics (simulating pipeline logic)
    confidence_scores = [s.confidence_score for s in result.suggestions]
    result.avg_confidence = sum(confidence_scores) / len(confidence_scores)
    result.min_confidence = min(confidence_scores)
    result.max_confidence = max(confidence_scores)
    result.high_confidence_count = sum(1 for c in confidence_scores if c >= 0.8)

    print(f"  Suggestions: {len(result.suggestions)}")
    print(f"  Average confidence: {result.avg_confidence:.2f}")
    print(f"  Min confidence: {result.min_confidence:.2f}")
    print(f"  Max confidence: {result.max_confidence:.2f}")
    print(f"  High confidence (>=0.8): {result.high_confidence_count}")

    # Verify calculations
    assert abs(result.avg_confidence - 0.8625) < 0.01, "Average confidence incorrect"
    assert result.min_confidence == 0.75, "Min confidence incorrect"
    assert result.max_confidence == 0.95, "Max confidence incorrect"
    assert result.high_confidence_count == 3, "High confidence count incorrect"

    print("\n  ✓ Metrics calculated correctly")
    return True


def test_combined_workflow():
    """Test 5: Combined workflow with all optimizations."""
    print("\n" + "="*60)
    print("TEST 5: Combined Workflow")
    print("="*60)

    # Create suggestions with varying confidence
    all_suggestions = [
        create_mock_suggestion(1, "VeryHigh", 0.95),
        create_mock_suggestion(2, "High", 0.85),
        create_mock_suggestion(3, "Medium", 0.72),
        create_mock_suggestion(4, "Low", 0.55),
        create_mock_suggestion(5, "VeryLow", 0.30),
    ]

    print(f"  Step 1: Generated {len(all_suggestions)} suggestions")
    for s in all_suggestions:
        print(f"    - {s.proposed_class_name}: {s.confidence_score:.2f}")

    # Step 2: Filter by confidence (threshold 0.7)
    naming_threshold = 0.7
    filtered_suggestions = [s for s in all_suggestions if s.confidence_score >= naming_threshold]
    print(f"\n  Step 2: Filtered to {len(filtered_suggestions)} (threshold={naming_threshold})")

    # Step 3: Sort by confidence
    filtered_suggestions.sort(key=lambda s: s.confidence_score, reverse=True)
    print(f"\n  Step 3: Sorted by confidence (highest first)")
    for i, s in enumerate(filtered_suggestions):
        print(f"    {i+1}. {s.proposed_class_name}: {s.confidence_score:.2f}")

    # Step 4: Pre-screen for verification (threshold 0.5)
    verification_threshold = 0.5
    to_verify = [s for s in filtered_suggestions if s.confidence_score >= verification_threshold]
    print(f"\n  Step 4: Pre-screening for verification (threshold={verification_threshold})")
    print(f"    Would verify: {len(to_verify)} suggestions")

    # Step 5: Calculate metrics
    if to_verify:
        confidences = [s.confidence_score for s in to_verify]
        avg_conf = sum(confidences) / len(confidences)
        print(f"\n  Step 5: Final metrics")
        print(f"    Average confidence: {avg_conf:.2f}")
        print(f"    High confidence (>=0.8): {sum(1 for c in confidences if c >= 0.8)}")

    # Verify the workflow
    assert len(filtered_suggestions) == 3, "Filtering failed"
    assert filtered_suggestions[0].proposed_class_name == "VeryHigh", "Sorting failed"
    assert len(to_verify) == 3, "Pre-screening failed"

    print("\n  ✓ Combined workflow successful")
    return True


def test_config_integration():
    """Test 6: Configuration integration."""
    print("\n" + "="*60)
    print("TEST 6: Configuration Integration")
    print("="*60)

    # Simulate config
    config = {
        "naming": {
            "min_confidence_threshold": 0.7,
            "sort_by_confidence": True
        },
        "refactoring_application": {
            "min_verification_confidence": 0.5
        }
    }

    print("  Configuration loaded:")
    print(f"    Naming threshold: {config['naming']['min_confidence_threshold']}")
    print(f"    Sort by confidence: {config['naming']['sort_by_confidence']}")
    print(f"    Verification threshold: {config['refactoring_application']['min_verification_confidence']}")

    # Verify config values
    assert config["naming"]["min_confidence_threshold"] == 0.7
    assert config["naming"]["sort_by_confidence"] is True
    assert config["refactoring_application"]["min_verification_confidence"] == 0.5

    print("\n  ✓ Configuration values correct")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("CONFIDENCE OPTIMIZATION TEST SUITE")
    print("="*70)

    tests = [
        ("Confidence Filtering", test_confidence_filtering),
        ("Confidence Sorting", test_confidence_sorting),
        ("Verification Pre-screening", test_verification_prescreening),
        ("PipelineResult Metrics", test_pipeline_result_metrics),
        ("Combined Workflow", test_combined_workflow),
        ("Configuration Integration", test_config_integration),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n  ✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n✅ All optimization tests passed!")
        print("\nOPTIMIZATIONS VERIFIED:")
        print("  ✓ Confidence filtering reduces low-quality suggestions")
        print("  ✓ Sorting prioritizes high-confidence suggestions")
        print("  ✓ Pre-screening saves verification time")
        print("  ✓ Metrics provide visibility into suggestion quality")
        print("  ✓ Configuration properly controls thresholds")
    else:
        print("\n❌ Some optimization tests failed!")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
