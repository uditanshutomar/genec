#!/usr/bin/env python3
"""
Test suite for Stage 5 LLM prompt engineering improvements.

Tests:
1. Prompt structure validation
2. Few-shot example presence
3. Chain-of-thought instructions
4. Class name validation (hallucination prevention)
5. Mock LLM response parsing
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from genec.core.llm_interface import LLMInterface, EXTRACT_CLASS_EXAMPLE
from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import ClassDependencies
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


def test_few_shot_example_structure():
    """Test 1: Verify few-shot example is well-structured."""
    print("\n" + "="*80)
    print("TEST 1: Few-Shot Example Structure")
    print("="*80)

    # Check example contains required elements
    required_elements = [
        '<example>',
        '<cluster_members>',
        '<reasoning>',
        'Step 1: Primary Responsibility Analysis',
        'Step 2: Shared Concept/Domain',
        'Step 3: Extraction Benefits',
        'Step 4: Design Justification',
        '<class_name>',
        '<rationale>',
        '</example>'
    ]

    for element in required_elements:
        assert element in EXTRACT_CLASS_EXAMPLE, f"Missing element: {element}"
        print(f"  ✓ Contains: {element}")

    print("\n✅ PASSED: Few-shot example is well-structured")
    return True


def test_prompt_contains_improvements():
    """Test 2: Verify prompt contains 2024 best practices."""
    print("\n" + "="*80)
    print("TEST 2: Prompt Improvements")
    print("="*80)

    # Create mock objects
    cluster = Cluster(
        id=1,
        member_names=["validateEmail(String)", "validatePhone(String)"],
        member_types={
            "validateEmail(String)": "method",
            "validatePhone(String)": "method"
        }
    )

    class_deps = ClassDependencies(
        class_name="UserService",
        package_name="com.example",
        file_path="UserService.java"
    )

    # Create interface (without API key - won't actually call LLM)
    interface = LLMInterface(api_key=None)

    # Build prompt
    prompt = interface._build_prompt(cluster, "", class_deps)

    # Check for improvements
    improvements = {
        'Few-shot example': 'FEW-SHOT EXAMPLE' in prompt,
        'Chain-of-thought': 'chain-of-thought reasoning' in prompt,
        'Step-by-step': 'Step 1:' in prompt and 'Step 2:' in prompt,
        'Quality guidelines': 'Quality Guidelines' in prompt,
        'Valid Java identifier': 'valid Java identifier' in prompt,
        'Single responsibility': 'single responsibility' in prompt,
        'Explicit instructions': 'Instructions:' in prompt,
        'Refactoring type': 'Extract Class' in prompt,
    }

    for improvement, present in improvements.items():
        status = "✓" if present else "✗"
        print(f"  {status} {improvement}: {present}")
        assert present, f"Missing improvement: {improvement}"

    print("\n✅ PASSED: Prompt contains all 2024 improvements")
    return True


def test_class_name_validation():
    """Test 3: Validate hallucination prevention."""
    print("\n" + "="*80)
    print("TEST 3: Class Name Validation (Hallucination Prevention)")
    print("="*80)

    interface = LLMInterface(api_key=None)

    # Valid names
    valid_names = [
        "InputValidator",
        "EmailProcessor",
        "DatabaseConnection",
        "JsonParser",
    ]

    for name in valid_names:
        result = interface._validate_class_name(name)
        print(f"  ✓ '{name}': {result}")
        assert result, f"Should accept valid name: {name}"

    # Invalid names
    invalid_names = [
        "helper",  # lowercase
        "AB",  # too short
        "Helper",  # too generic
        "Util",  # too generic
        "123Invalid",  # starts with number
        "Invalid Name",  # contains space
        "invalid-name",  # contains hyphen
    ]

    for name in invalid_names:
        result = interface._validate_class_name(name)
        print(f"  ✗ '{name}': {result}")
        assert not result, f"Should reject invalid name: {name}"

    print("\n✅ PASSED: Class name validation works correctly")
    return True


def test_response_parsing_with_reasoning():
    """Test 4: Parse LLM response with chain-of-thought reasoning."""
    print("\n" + "="*80)
    print("TEST 4: Response Parsing with Reasoning")
    print("="*80)

    interface = LLMInterface(api_key=None)

    cluster = Cluster(
        id=1,
        member_names=["test()"],
        member_types={"test()": "method"}
    )

    # Mock LLM response with reasoning
    mock_response = """
<reasoning>
Step 1: Primary Responsibility Analysis
These methods handle email validation using regex patterns.

Step 2: Shared Concept/Domain
They belong to the input validation domain.

Step 3: Extraction Benefits
- Improves single responsibility
- Enhances reusability
- Reduces complexity

Step 4: Design Justification
Follows Extract Class pattern for validation separation.
</reasoning>

<class_name>EmailValidator</class_name>

<rationale>
These methods form a cohesive validation unit for email processing.
They share validation patterns and have a clear responsibility.
</rationale>
"""

    suggestion = interface._parse_response(mock_response, cluster)

    assert suggestion is not None, "Should parse response successfully"
    assert suggestion.proposed_class_name == "EmailValidator"
    assert "validation" in suggestion.rationale.lower()

    print(f"  ✓ Class name: {suggestion.proposed_class_name}")
    print(f"  ✓ Rationale: {suggestion.rationale[:80]}...")
    print("\n✅ PASSED: Response parsing with reasoning works")
    return True


def test_prompt_length():
    """Test 5: Verify prompt is not excessively long."""
    print("\n" + "="*80)
    print("TEST 5: Prompt Length Check")
    print("="*80)

    cluster = Cluster(
        id=1,
        member_names=[f"method{i}()" for i in range(10)],
        member_types={f"method{i}()": "method" for i in range(10)}
    )

    class_deps = ClassDependencies(
        class_name="TestClass",
        package_name="com.test",
        file_path="TestClass.java"
    )

    interface = LLMInterface(api_key=None)
    prompt = interface._build_prompt(cluster, "", class_deps)

    prompt_length = len(prompt)
    token_estimate = prompt_length // 4  # Rough estimate

    print(f"  Prompt length: {prompt_length} characters")
    print(f"  Estimated tokens: ~{token_estimate}")

    # Should be reasonable (not exceeding typical context limits)
    assert prompt_length < 10000, "Prompt is too long"
    print(f"  ✓ Prompt length acceptable")

    print("\n✅ PASSED: Prompt length is reasonable")
    return True


def run_all_tests():
    """Run all Stage 5 improvement tests."""
    print("\n" + "="*80)
    print("STAGE 5 LLM PROMPT ENGINEERING - TEST SUITE")
    print("="*80)

    tests = [
        ("Few-Shot Example Structure", test_few_shot_example_structure),
        ("Prompt Improvements", test_prompt_contains_improvements),
        ("Class Name Validation", test_class_name_validation),
        ("Response Parsing with Reasoning", test_response_parsing_with_reasoning),
        ("Prompt Length Check", test_prompt_length),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            logger.error(f"Test '{test_name}' raised exception: {e}", exc_info=True)
            results.append((test_name, False))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")

    print("="*80)
    print(f"Total: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
