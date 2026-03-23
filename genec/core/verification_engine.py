"""Multi-layer verification engine for refactoring suggestions."""

import os

from genec.core.dependency_analyzer import ClassDependencies
from genec.core.models import RefactoringSuggestion, VerificationResult
from genec.utils.logging_utils import get_logger
from genec.verification.behavioral_verifier import BehavioralVerifier
from genec.verification.equivalence_checker import EquivalenceChecker
from genec.verification.multiversion_compiler import MultiVersionCompilationVerifier  # NEW
from genec.verification.performance_verifier import PerformanceVerifier  # NEW
from genec.verification.semantic_verifier import SemanticVerifier
from genec.verification.static_analysis_verifier import StaticAnalysisVerifier
from genec.verification.syntactic_verifier import SyntacticVerifier

logger = get_logger(__name__)


class VerificationEngine:
    """Orchestrates multi-layer verification of refactoring suggestions."""

    def __init__(
        self,
        enable_equivalence: bool = True,
        enable_syntactic: bool = True,
        enable_static_analysis: bool = False,
        enable_multiversion: bool = False,  # NEW
        enable_semantic: bool = True,
        enable_behavioral: bool = True,
        enable_performance: bool = False,  # NEW
        enable_coverage: bool = False,  # NEW
        java_compiler: str = "javac",
        maven_command: str = "mvn",
        gradle_command: str = "gradle",
        build_tool: str = "maven",
        repo_path: str | None = None,
        lenient_mode: bool = True,
    ):
        """
        Initialize verification engine.
        """
        self.enable_equivalence = enable_equivalence
        self.enable_syntactic = enable_syntactic
        self.enable_static_analysis = enable_static_analysis
        self.enable_multiversion = enable_multiversion
        self.enable_semantic = enable_semantic
        self.enable_behavioral = enable_behavioral
        self.enable_performance = enable_performance
        self.enable_coverage = enable_coverage

        # Initialize verifiers
        self.equivalence_checker = EquivalenceChecker(build_tool=build_tool)
        self.syntactic_verifier = SyntacticVerifier(java_compiler, repo_path, lenient_mode=lenient_mode)
        self.static_analysis_verifier = StaticAnalysisVerifier()
        self.multiversion_compiler = MultiVersionCompilationVerifier()  # NEW
        self.semantic_verifier = SemanticVerifier()
        self.behavioral_verifier = BehavioralVerifier(
            maven_command, gradle_command, check_coverage=enable_coverage
        )
        self.performance_verifier = PerformanceVerifier()  # NEW

        self.logger = get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Individual verification layer helpers
    # ------------------------------------------------------------------

    def _run_equivalence_check(
        self,
        suggestion: RefactoringSuggestion,
        original_class_file: str,
        repo_path: str,
        class_deps: ClassDependencies,
        result: VerificationResult,
    ) -> bool:
        """Layer 0: Equivalence checking. Returns True if check ran."""
        if not self.enable_equivalence:
            self.logger.info("Equivalence checking skipped (equivalence_pass left as False)")
            return False

        self.logger.info("Layer 0: Equivalence Checking (Behavioral Preservation)")

        package_path = class_deps.package_name.replace(".", os.sep)
        new_class_path = os.path.join(
            "src", "main", "java", package_path, f"{suggestion.proposed_class_name}.java"
        )
        refactored_files = {
            new_class_path: suggestion.new_class_code,
            original_class_file: suggestion.modified_original_code,
        }

        equiv_result = self.equivalence_checker.check_equivalence(
            original_class_file=original_class_file,
            refactored_files=refactored_files,
            repo_path=repo_path,
            cluster=suggestion.cluster,
            suggestion=suggestion,
        )

        result.equivalence_pass = equiv_result.is_equivalent
        result.tests_run = equiv_result.tests_run

        if not equiv_result.is_equivalent:
            result.status = "FAILED_EQUIVALENCE"
            result.error_message = (
                f"Behavioral differences detected: {', '.join(equiv_result.differing_tests[:5])}"
            )
            self.logger.warning(f"Equivalence checking failed: {result.error_message}")
        else:
            self.logger.info(f"Equivalence verified ({equiv_result.tests_run} tests passed)")

        return True

    def _run_syntactic_check(
        self,
        suggestion: RefactoringSuggestion,
        class_deps: ClassDependencies,
        result: VerificationResult,
        original_class_file: str = "",
    ) -> None:
        """Layer 1: Syntactic verification."""
        if not self.enable_syntactic:
            # Layer skipped — *_pass left as default (False).
            # is_valid checks status field, not individual pass flags.
            result.syntactic_pass = True
            self.logger.info("Syntactic verification skipped")
            return

        self.logger.info("Layer 1: Syntactic Verification")

        syntactic_pass, error = self.syntactic_verifier.verify(
            suggestion.new_class_code,
            suggestion.modified_original_code,
            class_deps.package_name,
            original_class_file=original_class_file or None,
            new_class_name=suggestion.proposed_class_name,
        )

        result.syntactic_pass = syntactic_pass
        if not syntactic_pass:
            result.status = "FAILED_SYNTACTIC"
            result.error_message = error
            self.logger.warning(f"Syntactic verification failed: {error}")

    def _run_static_analysis_check(
        self,
        suggestion: RefactoringSuggestion,
        original_code: str,
        repo_path: str,
        class_deps: ClassDependencies,
        result: VerificationResult,
    ) -> None:
        """Layer 1.5: Static analysis (code quality)."""
        if not self.enable_static_analysis:
            # Layer skipped — *_pass left as default (False).
            # is_valid checks status field, not individual pass flags.
            result.quality_pass = True
            self.logger.info("Static analysis skipped")
            return

        self.logger.info("Layer 1.5: Static Analysis (Code Quality)")

        quality_pass, error = self.static_analysis_verifier.verify(
            original_code,
            suggestion.new_class_code,
            suggestion.modified_original_code,
            repo_path,
            class_deps.package_name,
        )

        result.quality_pass = quality_pass
        if not quality_pass:
            result.status = "FAILED_QUALITY"
            result.error_message = error
            self.logger.warning(f"Static analysis failed: {error}")
        else:
            self.logger.info("Static analysis passed (no quality regression)")

    def _run_multiversion_check(
        self,
        suggestion: RefactoringSuggestion,
        class_deps: ClassDependencies,
        result: VerificationResult,
    ) -> None:
        """Layer 1.7: Multi-version compilation."""
        if not self.enable_multiversion:
            # Layer skipped — *_pass left as default (False).
            # is_valid checks status field, not individual pass flags.
            result.multiversion_pass = True
            self.logger.info("Multi-version compilation skipped")
            return

        self.logger.info("Layer 1.7: Multi-Version Compilation")

        multiversion_pass, error = self.multiversion_compiler.verify(
            suggestion.new_class_code,
            suggestion.modified_original_code,
            class_deps.package_name,
            class_deps.class_name,
        )

        result.multiversion_pass = multiversion_pass
        if not multiversion_pass:
            result.status = "FAILED_MULTIVERSION"
            result.error_message = error
            self.logger.warning(f"Multi-version compilation failed: {error}")
        else:
            self.logger.info("Multi-version compilation passed")

    def _run_semantic_check(
        self,
        suggestion: RefactoringSuggestion,
        original_code: str,
        class_deps: ClassDependencies,
        result: VerificationResult,
    ) -> None:
        """Layer 2: Semantic verification."""
        if not self.enable_semantic:
            # Layer skipped — *_pass left as default (False).
            # is_valid checks status field, not individual pass flags.
            result.semantic_pass = True
            self.logger.info("Semantic verification skipped")
            return

        self.logger.info("Layer 2: Semantic Verification")

        semantic_pass, error = self.semantic_verifier.verify(
            original_code,
            suggestion.new_class_code,
            suggestion.modified_original_code,
            suggestion.cluster,
            class_deps,
        )

        result.semantic_pass = semantic_pass
        if not semantic_pass:
            result.status = "FAILED_SEMANTIC"
            result.error_message = error
            self.logger.warning(f"Semantic verification failed: {error}")

    def _run_behavioral_check(
        self,
        suggestion: RefactoringSuggestion,
        original_class_file: str,
        repo_path: str,
        class_deps: ClassDependencies,
        result: VerificationResult,
        equivalence_ran: bool,
    ) -> None:
        """Layer 3: Behavioral verification (skipped when equivalence already ran)."""
        if self.enable_behavioral and not equivalence_ran:
            self.logger.info("Layer 3: Behavioral Verification")

            behavioral_pass, error = self.behavioral_verifier.verify(
                original_class_file,
                suggestion.new_class_code,
                suggestion.modified_original_code,
                repo_path,
                class_deps.package_name,
            )

            result.behavioral_pass = behavioral_pass
            if not behavioral_pass:
                result.status = "FAILED_BEHAVIORAL"
                result.error_message = error
                self.logger.warning(f"Behavioral verification failed: {error}")
        elif self.enable_behavioral and equivalence_ran and result.equivalence_pass:
            result.behavioral_pass = True
            self.logger.info("Behavioral verification skipped (equivalence already verified)")
        else:
            # Layer skipped — *_pass left as default (False).
            # is_valid checks status field, not individual pass flags.
            result.behavioral_pass = True
            self.logger.info("Behavioral verification skipped")

    def _run_performance_check(
        self,
        suggestion: RefactoringSuggestion,
        original_code: str,
        repo_path: str,
        class_deps: ClassDependencies,
        result: VerificationResult,
    ) -> None:
        """Layer 4: Performance verification."""
        if not self.enable_performance:
            # Layer skipped — *_pass left as default (False).
            # is_valid checks status field, not individual pass flags.
            result.performance_pass = True
            self.logger.info("Performance verification skipped")
            return

        self.logger.info("Layer 4: Performance Verification")

        perf_pass, perf_error = self.performance_verifier.verify(
            original_code,
            suggestion.new_class_code,
            suggestion.modified_original_code,
            repo_path,
            class_deps.class_name,
        )

        result.performance_pass = perf_pass
        if perf_error:
            result.performance_regression = 1.0

        if not perf_pass:
            result.status = "FAILED_PERFORMANCE"
            result.error_message = perf_error
            self.logger.warning(f"Performance verification failed: {perf_error}")
        else:
            self.logger.info("Performance verification passed (no regression)")

    # ------------------------------------------------------------------
    # Main orchestrator
    # ------------------------------------------------------------------

    def verify_refactoring(
        self,
        suggestion: RefactoringSuggestion,
        original_code: str,
        original_class_file: str,
        repo_path: str,
        class_deps: ClassDependencies,
    ) -> VerificationResult:
        """
        Perform multi-layer verification on a refactoring suggestion.

        Verification layers:
        0. Equivalence: Do all tests produce identical outputs?
        1. Syntactic: Does the code compile?
        1.5. Static Analysis: No quality regression?
        1.7. Multi-Version: Compiles on multiple Java versions?
        2. Semantic: Is it a valid Extract Class refactoring?
        3. Behavioral: Do all tests still pass?
        4. Performance: No performance regression?

        Returns:
            VerificationResult with detailed status
        """
        self.logger.info(f"Verifying refactoring suggestion: {suggestion.proposed_class_name}")
        result = VerificationResult(suggestion_id=suggestion.cluster_id, status="PENDING")

        # Each layer sets fields on `result` and marks status on failure.
        # We return early whenever a layer fails.

        equivalence_ran = self._run_equivalence_check(
            suggestion, original_class_file, repo_path, class_deps, result
        )
        if result.status.startswith("FAILED"):
            return result

        self._run_syntactic_check(suggestion, class_deps, result, original_class_file)
        if result.status.startswith("FAILED"):
            return result

        self._run_static_analysis_check(suggestion, original_code, repo_path, class_deps, result)
        if result.status.startswith("FAILED"):
            return result

        self._run_multiversion_check(suggestion, class_deps, result)
        if result.status.startswith("FAILED"):
            return result

        self._run_semantic_check(suggestion, original_code, class_deps, result)
        if result.status.startswith("FAILED"):
            return result

        self._run_behavioral_check(
            suggestion, original_class_file, repo_path, class_deps, result, equivalence_ran
        )
        if result.status.startswith("FAILED"):
            return result

        self._run_performance_check(suggestion, original_code, repo_path, class_deps, result)
        if result.status.startswith("FAILED"):
            return result

        result.status = "PASSED_ALL"
        self.logger.info("All verification layers PASSED")
        return result

    def check_prerequisites(self) -> dict:
        """
        Check if all required tools are available.

        Returns:
            Dict with status of each tool
        """
        status = {}

        # Check Java compiler
        status["java_compiler"] = self.syntactic_verifier.check_compiler_available()

        # Check build tools
        build_tools = self.behavioral_verifier.check_build_tools_available()
        status.update(build_tools)

        return status
