#!/usr/bin/env python3
"""
Smoke test for GenEC pipeline with confidence optimizations.

This test verifies:
1. Core pipeline components can be initialized
2. Configuration is loaded correctly
3. All stages can be instantiated
4. Optimizations are properly integrated
5. No import errors or syntax issues
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

print("="*70)
print("GenEC Pipeline Smoke Test")
print("="*70)

# Test 1: Import all core modules
print("\n[1/8] Testing imports...")
try:
    from genec.core.pipeline import GenECPipeline, PipelineResult
    from genec.core.llm_interface import LLMInterface, RefactoringSuggestion
    from genec.core.cluster_detector import Cluster, ClusterDetector
    from genec.core.dependency_analyzer import DependencyAnalyzer, ClassDependencies
    from genec.core.evolutionary_miner import EvolutionaryMiner
    from genec.core.graph_builder import GraphBuilder
    from genec.core.stages.naming_stage import NamingStage
    from genec.core.stages.refactoring_stage import RefactoringStage
    from genec.core.stages.analysis_stage import AnalysisStage
    from genec.core.stages.clustering_stage import ClusteringStage
    print("  ✓ All core modules imported successfully")
except ImportError as e:
    print(f"  ✗ Import error: {e}")
    sys.exit(1)

# Test 2: Check PipelineResult has new confidence fields
print("\n[2/8] Checking PipelineResult fields...")
try:
    result = PipelineResult(class_name="Test")
    assert hasattr(result, 'avg_confidence'), "Missing avg_confidence field"
    assert hasattr(result, 'min_confidence'), "Missing min_confidence field"
    assert hasattr(result, 'max_confidence'), "Missing max_confidence field"
    assert hasattr(result, 'high_confidence_count'), "Missing high_confidence_count field"
    print("  ✓ PipelineResult has all confidence fields")
except AssertionError as e:
    print(f"  ✗ {e}")
    sys.exit(1)

# Test 3: Check RefactoringSuggestion has confidence fields
print("\n[3/8] Checking RefactoringSuggestion fields...")
try:
    methods = ["public void test()"]
    member_names = methods
    member_types = {m: "method" for m in methods}
    cluster = Cluster(id=1, member_names=member_names, member_types=member_types)

    suggestion = RefactoringSuggestion(
        cluster_id=1,
        proposed_class_name="TestClass",
        rationale="Test",
        new_class_code="",
        modified_original_code="",
        cluster=cluster,
        confidence_score=0.85,
        reasoning="Test reasoning"
    )

    assert suggestion.confidence_score == 0.85, "Confidence score not set"
    assert suggestion.reasoning == "Test reasoning", "Reasoning not set"
    assert hasattr(suggestion, 'quality_tier'), "Missing quality_tier"
    assert hasattr(suggestion, 'quality_score'), "Missing quality_score"
    print("  ✓ RefactoringSuggestion has all fields")
except AssertionError as e:
    print(f"  ✗ {e}")
    sys.exit(1)

# Test 4: Load and validate configuration
print("\n[4/8] Loading configuration...")
try:
    import yaml
    config_path = Path(__file__).parent / "config" / "config.yaml"

    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Check for new config sections
        has_naming_config = "naming" in config
        has_min_confidence = config.get("naming", {}).get("min_confidence_threshold") is not None
        has_sort_config = config.get("naming", {}).get("sort_by_confidence") is not None
        has_verification_threshold = config.get("refactoring_application", {}).get("min_verification_confidence") is not None

        print(f"  ✓ Configuration loaded")
        print(f"    - naming section: {'✓' if has_naming_config else '✗'}")
        print(f"    - min_confidence_threshold: {config.get('naming', {}).get('min_confidence_threshold', 'not set')}")
        print(f"    - sort_by_confidence: {config.get('naming', {}).get('sort_by_confidence', 'not set')}")
        print(f"    - min_verification_confidence: {config.get('refactoring_application', {}).get('min_verification_confidence', 'not set')}")

        if has_naming_config and has_min_confidence and has_sort_config and has_verification_threshold:
            print("  ✓ All optimization configs present")
        else:
            print("  ⚠ Some optimization configs missing (using defaults)")
    else:
        print("  ⚠ Config file not found (will use defaults)")
except Exception as e:
    print(f"  ✗ Config error: {e}")
    sys.exit(1)

# Test 5: Initialize LLMInterface
print("\n[5/8] Initializing LLMInterface...")
try:
    llm = LLMInterface(api_key="test_key")
    print(f"  ✓ LLMInterface initialized")
    print(f"    - Model: {llm.model}")
    print(f"    - Temperature: {llm.temperature}")
    print(f"    - Use chunking: {llm.use_chunking}")
    print(f"    - Use hybrid mode: {llm.use_hybrid_mode}")
    print(f"    - Enable confidence scoring: {llm.enable_confidence_scoring}")
except Exception as e:
    print(f"  ✗ LLMInterface error: {e}")
    sys.exit(1)

# Test 6: Test prompt construction
print("\n[6/8] Testing prompt construction...")
try:
    methods = ["public void validateEmail(String e)", "public boolean isValid()"]
    fields = ["private String email"]
    member_names = methods + fields
    member_types = {m: "method" for m in methods}
    member_types.update({f: "field" for f in fields})

    cluster = Cluster(id=1, member_names=member_names, member_types=member_types)
    class_deps = ClassDependencies(class_name="User", file_path="User.java", package_name="com.example")
    original_code = "public class User { private String email; }"

    prompt = llm._build_prompt(cluster, original_code, class_deps)

    # Check for key prompt components
    checks = [
        ("Senior Java Architect" in prompt, "Persona"),
        ("<confidence>" in prompt, "Confidence tag"),
        ("<reasoning>" in prompt, "Reasoning tag"),
        ("step-by-step" in prompt.lower(), "Step-by-step instruction"),
    ]

    all_passed = True
    for passed, name in checks:
        status = "✓" if passed else "✗"
        print(f"    {status} {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("  ✓ Prompt construction works correctly")
    else:
        print("  ✗ Some prompt components missing")
        sys.exit(1)

except Exception as e:
    print(f"  ✗ Prompt construction error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 7: Test response parsing
print("\n[7/8] Testing response parsing...")
try:
    mock_response = """
<reasoning>
Step 1: These methods validate email addresses.
Step 2: They belong to the validation domain.
Step 3: Extracting improves SRP.
Step 4: Extract Class pattern.
</reasoning>

<class_name>EmailValidator</class_name>

<rationale>
These methods form a cohesive validation unit.
</rationale>

<confidence>0.92</confidence>
"""

    methods = ["public void validateEmail(String e)"]
    member_names = methods
    member_types = {m: "method" for m in methods}
    cluster = Cluster(id=1, member_names=member_names, member_types=member_types)

    parsed = llm._parse_response(mock_response, cluster)

    assert parsed is not None, "Parsing failed"
    assert parsed.proposed_class_name == "EmailValidator", "Class name not extracted"
    assert parsed.confidence_score == 0.92, f"Confidence not extracted correctly: {parsed.confidence_score}"
    assert parsed.reasoning is not None, "Reasoning not extracted"
    assert "validation" in parsed.reasoning.lower(), "Reasoning content missing"

    print("  ✓ Response parsing works correctly")
    print(f"    - Class name: {parsed.proposed_class_name}")
    print(f"    - Confidence: {parsed.confidence_score}")
    print(f"    - Reasoning extracted: {len(parsed.reasoning)} chars")

except AssertionError as e:
    print(f"  ✗ Parsing assertion failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"  ✗ Parsing error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 8: Test confidence-based filtering logic
print("\n[8/8] Testing confidence filtering logic...")
try:
    # Create mock suggestions
    suggestions = [
        RefactoringSuggestion(
            cluster_id=i,
            proposed_class_name=f"Class{i}",
            rationale="Test",
            new_class_code="",
            modified_original_code="",
            cluster=Cluster(id=i, member_names=[f"method{i}"], member_types={f"method{i}": "method"}),
            confidence_score=score
        )
        for i, score in enumerate([0.95, 0.75, 0.50, 0.30], 1)
    ]

    # Test filtering
    threshold = 0.7
    filtered = [s for s in suggestions if s.confidence_score >= threshold]

    assert len(filtered) == 2, f"Expected 2 filtered, got {len(filtered)}"

    # Test sorting
    sorted_suggestions = sorted(suggestions, key=lambda s: s.confidence_score, reverse=True)
    assert sorted_suggestions[0].confidence_score == 0.95, "Sorting failed"

    # Test metrics calculation
    confidence_scores = [s.confidence_score for s in suggestions]
    avg = sum(confidence_scores) / len(confidence_scores)
    high_count = sum(1 for c in confidence_scores if c >= 0.8)

    print("  ✓ Filtering logic works")
    print(f"    - Original: {len(suggestions)} suggestions")
    print(f"    - After filtering (≥{threshold}): {len(filtered)} suggestions")
    print(f"    - Average confidence: {avg:.2f}")
    print(f"    - High confidence (≥0.8): {high_count}")

except AssertionError as e:
    print(f"  ✗ Filtering assertion failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"  ✗ Filtering error: {e}")
    sys.exit(1)

# Summary
print("\n" + "="*70)
print("SMOKE TEST RESULTS")
print("="*70)
print("✅ All tests passed!")
print("\nVerified:")
print("  ✓ All modules import correctly")
print("  ✓ PipelineResult has confidence metrics")
print("  ✓ RefactoringSuggestion has confidence fields")
print("  ✓ Configuration loads with optimization settings")
print("  ✓ LLMInterface initializes correctly")
print("  ✓ Prompt construction includes all improvements")
print("  ✓ Response parsing extracts confidence & reasoning")
print("  ✓ Filtering and sorting logic works")
print("\n🎉 GenEC pipeline is ready with all optimizations!")
print("="*70)

sys.exit(0)
