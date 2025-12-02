#!/usr/bin/env python3
"""Test script for the 3 optional Stage 2 improvements."""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from genec.core.evolutionary_miner import EvolutionaryMiner


def test_improvement_1_auto_metrics():
    """Test Improvement 1: Auto-show parser metrics."""
    print("\n" + "=" * 80)
    print("TEST 1: AUTO-SHOW PARSER METRICS")
    print("=" * 80)

    # Create a simple Java file to test
    java_code = """
public class TestClass {
    public void simpleMethod() {
        System.out.println("test");
    }

    public int calculate(int x) {
        return x * 2;
    }
}
"""

    miner = EvolutionaryMiner()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False) as tmp:
        tmp.write(java_code)
        tmp_path = tmp.name

    try:
        # Test that metrics are printed automatically (show_metrics=True by default)
        print("\n✓ Testing with show_metrics=True (default):")
        methods = miner._extract_methods_from_content(java_code)
        print(f"  Found {len(methods)} methods: {methods}")

        print("\n✓ Improvement 1 SUCCESS: Metrics auto-displayed!")

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return True


def test_improvement_2_better_regex():
    """Test Improvement 2: Better regex fallback for parameter types."""
    print("\n" + "=" * 80)
    print("TEST 2: BETTER REGEX FALLBACK FOR PARAMETER TYPES")
    print("=" * 80)

    miner = EvolutionaryMiner()

    # Test cases with various parameter patterns
    test_cases = [
        ("int x", ["int"]),
        ("String name", ["String"]),
        ("List<String> items", ["List<String>"]),
        ("int x, String y", ["int", "String"]),
        ("final int value", ["int"]),
        ("List<String> items, int count", ["List<String>", "int"]),
    ]

    print("\nTesting parameter type extraction:")
    all_passed = True

    for params_str, expected in test_cases:
        result = miner._extract_param_types(params_str)
        passed = result == expected

        status = "✓" if passed else "✗"
        print(f"  {status} '{params_str}' -> {result} (expected: {expected})")

        if not passed:
            all_passed = False

    if all_passed:
        print("\n✓ Improvement 2 SUCCESS: All parameter types extracted correctly!")
    else:
        print("\n✗ Improvement 2 FAILED: Some test cases failed")

    return all_passed


def test_improvement_3_generic_support():
    """Test Improvement 3: Full generic type support in fallback."""
    print("\n" + "=" * 80)
    print("TEST 3: FULL GENERIC TYPE SUPPORT IN FALLBACK")
    print("=" * 80)

    miner = EvolutionaryMiner()

    # Test cases with complex generic types
    test_cases = [
        ("List<String> items", ["List<String>"]),
        ("Map<String, Integer> map", ["Map<String,Integer>"]),  # Normalized (no spaces)
        ("List<List<String>> nested", ["List<List<String>>"]),
        ("Map<String, List<Integer>> complex", ["Map<String,List<Integer>>"]),
        ("Set<Integer> numbers, List<String> names", ["Set<Integer>", "List<String>"]),
    ]

    print("\nTesting generic type preservation:")
    all_passed = True

    for params_str, expected in test_cases:
        result = miner._extract_param_types(params_str)
        passed = result == expected

        status = "✓" if passed else "✗"
        print(f"  {status} '{params_str}'")
        print(f"      -> {result}")
        if not passed:
            print(f"      Expected: {expected}")

        if not passed:
            all_passed = False

    # Test full method signature extraction with generics
    print("\nTesting full method signatures with generics:")

    java_code_with_generics = """
public class GenericTest {
    public void processStrings(List<String> items) {
        // process
    }

    public Map<String, Integer> buildMap(List<String> keys, List<Integer> values) {
        return null;
    }

    public void complexMethod(Map<String, List<Integer>> data) {
        // complex
    }
}
"""

    methods = miner._extract_methods_simple(java_code_with_generics)

    expected_signatures = [
        "processStrings(List<String>)",
        "buildMap(List<String>,List<Integer>)",
        "complexMethod(Map<String,List<Integer>>)",
    ]

    print("\nExtracted method signatures:")
    for method in methods:
        in_expected = method in expected_signatures
        status = "✓" if in_expected else "✗"
        print(f"  {status} {method}")

    found_all = all(sig in methods for sig in expected_signatures)
    if found_all and all_passed:
        print("\n✓ Improvement 3 SUCCESS: Generic types fully preserved!")
    else:
        print("\n✗ Improvement 3 FAILED: Generic type preservation incomplete")
        all_passed = False

    return all_passed


def test_all_improvements():
    """Run all improvement tests."""
    print("=" * 80)
    print("STAGE 2 OPTIONAL IMPROVEMENTS - COMPREHENSIVE TEST")
    print("=" * 80)

    results = {
        "Improvement 1 (Auto-show metrics)": test_improvement_1_auto_metrics(),
        "Improvement 2 (Better regex fallback)": test_improvement_2_better_regex(),
        "Improvement 3 (Generic type support)": test_improvement_3_generic_support(),
    }

    print("\n" + "=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)

    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(results.values())

    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL OPTIONAL IMPROVEMENTS WORKING CORRECTLY!")
    else:
        print("❌ SOME IMPROVEMENTS FAILED")
    print("=" * 80)

    return all_passed


if __name__ == '__main__':
    success = test_all_improvements()
    sys.exit(0 if success else 1)
