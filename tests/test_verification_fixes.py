"""
Test verification fixes for delegation detection and warning handling.
"""

import pytest
from genec.verification.semantic_verifier import SemanticVerifier
from genec.verification.behavioral_verifier import BehavioralVerifier


class TestDelegationDetection:
    """Test semantic verifier delegation detection improvements."""

    def test_generic_method_delegation_detection(self):
        """Test that generic methods with throws clauses are detected as delegation."""
        verifier = SemanticVerifier()

        # Code with generic method delegation (multi-line, throws clause)
        source = """
        package com.example;

        public class ArrayUtils {
            private static <T, R, E extends Throwable> R[] map(final T[] array, final Class<R> componentType, final FailableFunction<? super T, ? extends R, E> mapper)
                    throws E {
                return GenericArrayOperations.map(array, componentType, mapper);
            }

            public static <T> T[] insert(int index, T[] array, T... elements) {
                return GenericArrayOperations.insert(index, array, elements);
            }
        }
        """

        # Test delegation detection
        assert verifier._is_delegation_by_source(source, "map")
        assert verifier._is_delegation_by_source(source, "insert")

    def test_simple_method_delegation_detection(self):
        """Test that simple methods are still detected correctly."""
        verifier = SemanticVerifier()

        source = """
        public class Test {
            public void add(int x) {
                return helper.add(x);
            }
        }
        """

        assert verifier._is_delegation_by_source(source, "add")

    def test_non_delegation_not_detected(self):
        """Test that actual implementation is not detected as delegation."""
        verifier = SemanticVerifier()

        source = """
        public class Test {
            public int add(int x, int y) {
                int result = x + y;
                return result;
            }
        }
        """

        assert not verifier._is_delegation_by_source(source, "add")


class TestWarningHandling:
    """Test behavioral verifier warning vs failure detection."""

    def test_warnings_only_detected_correctly(self):
        """Test that Maven/JDK warnings are not treated as failures."""
        verifier = BehavioralVerifier()

        warning_output = """WARNING: A terminally deprecated method in sun.misc.Unsafe has been called
WARNING: sun.misc.Unsafe::staticFieldBase has been called by com.google.inject.internal.aop.HiddenClassDefiner
WARNING: Please consider reporting this to the maintainers of class com.google.inject.internal.aop.HiddenClassDefiner
WARNING: sun.misc.Unsafe::staticFieldBase will be removed in a future release
WARNING: Use of the three-letter time zone ID "ACT" is deprecated and it will be removed in a future release
"""

        assert verifier._only_contains_warnings(warning_output)

    def test_test_failures_detected(self):
        """Test that actual test failures are detected."""
        verifier = BehavioralVerifier()

        failure_output = """Tests run: 100, Failures: 5, Errors: 2, Skipped: 0"""

        assert not verifier._only_contains_warnings(failure_output)

    def test_build_failure_detected(self):
        """Test that build failures are detected."""
        verifier = BehavioralVerifier()

        failure_output = """[ERROR] BUILD FAILURE
[ERROR] Compilation error: cannot find symbol"""

        assert not verifier._only_contains_warnings(failure_output)

    def test_empty_output_treated_as_success(self):
        """Test that empty output is not treated as failure."""
        verifier = BehavioralVerifier()

        assert verifier._only_contains_warnings("")
        assert verifier._only_contains_warnings("   \n  \t  ")

    def test_successful_test_results_with_zero_failures(self):
        """Test that successful test results are correctly identified."""
        verifier = BehavioralVerifier()

        success_output = """Tests run: 1234, Failures: 0, Errors: 0, Skipped: 10"""

        assert verifier._only_contains_warnings(success_output)
