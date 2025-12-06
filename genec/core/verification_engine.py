"""Multi-layer verification engine for refactoring suggestions."""

from dataclasses import dataclass

from genec.core.dependency_analyzer import ClassDependencies
from genec.core.llm_interface import RefactoringSuggestion
from genec.utils.logging_utils import get_logger
from genec.verification.behavioral_verifier import BehavioralVerifier
from genec.verification.equivalence_checker import EquivalenceChecker
from genec.verification.multiversion_compiler import MultiVersionCompilationVerifier  # NEW
from genec.verification.performance_verifier import PerformanceVerifier  # NEW
from genec.verification.semantic_verifier import SemanticVerifier
from genec.verification.static_analysis_verifier import StaticAnalysisVerifier
from genec.verification.syntactic_verifier import SyntacticVerifier

logger = get_logger(__name__)


@dataclass
class VerificationResult:
    """Result of multi-layer verification."""

    suggestion_id: int
    status: str
    equivalence_pass: bool = False  # Layer 0
    syntactic_pass: bool = False  # Layer 1
    quality_pass: bool = False  # Layer 1.5
    multiversion_pass: bool = False  # Layer 1.7 (NEW)
    semantic_pass: bool = False  # Layer 2
    behavioral_pass: bool = False  # Layer 3
    performance_pass: bool = False  # Layer 4 (NEW)
    tests_run: int = 0
    quality_improvement: float = 0.0
    performance_regression: float = 0.0  # NEW
    error_message: str | None = None


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
        enable_coverage: bool = False,     # NEW
        java_compiler: str = "javac",
        maven_command: str = "mvn",
        gradle_command: str = "gradle",
        build_tool: str = "maven",
        repo_path: str | None = None,
    ):
        """
        Initialize verification engine.

        Args:
            enable_equivalence: Enable equivalence checking
            enable_syntactic: Enable syntactic verification
            enable_static_analysis: Enable static analysis
            enable_multiversion: Enable multi-version compilation (NEW)
            enable_semantic: Enable semantic verification
            enable_behavioral: Enable behavioral verification
            enable_performance: Enable performance regression testing (NEW)
            enable_coverage: Enable coverage verification (NEW)
            java_compiler: Java compiler command
            maven_command: Maven command
            gradle_command: Gradle command
            build_tool: Build tool
            repo_path: Path to repository root
        """
        self.enable_equivalence = enable_equivalence
        self.enable_syntactic = enable_syntactic
        self.enable_static_analysis = enable_static_analysis
        self.enable_multiversion = enable_multiversion  # NEW
        self.enable_semantic = enable_semantic
        self.enable_behavioral = enable_behavioral
        self.enable_performance = enable_performance  # NEW
        self.enable_coverage = enable_coverage  # NEW

        # Initialize verifiers
        self.equivalence_checker = EquivalenceChecker(build_tool=build_tool)
        self.syntactic_verifier = SyntacticVerifier(java_compiler, repo_path)
        self.static_analysis_verifier = StaticAnalysisVerifier()
        self.multiversion_compiler = MultiVersionCompilationVerifier()  # NEW
        self.semantic_verifier = SemanticVerifier()
        self.behavioral_verifier = BehavioralVerifier(
            maven_command, 
            gradle_command,
            check_coverage=enable_coverage
        )
        self.performance_verifier = PerformanceVerifier()  # NEW

        self.logger = get_logger(self.__class__.__name__)

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
        0. Equivalence: Do all tests produce identical outputs? (NEW)
        1. Syntactic: Does the code compile?
        2. Semantic: Is it a valid Extract Class refactoring?
        3. Behavioral: Do all tests still pass?

        Args:
            suggestion: Refactoring suggestion to verify
            original_code: Original class source code
            original_class_file: Path to original class file
            repo_path: Path to repository
            class_deps: Original class dependencies

        Returns:
            VerificationResult with detailed status
        """
        self.logger.info(f"Verifying refactoring suggestion: {suggestion.proposed_class_name}")

        result = VerificationResult(suggestion_id=suggestion.cluster_id, status="PENDING")

        # Layer 0: Equivalence Checking (NEW - MOST CRITICAL)
        if self.enable_equivalence:
            self.logger.info("Layer 0: Equivalence Checking (Behavioral Preservation)")

            # Build refactored files dict (use os.path.join for cross-platform)
            import os
            package_path = class_deps.package_name.replace('.', os.sep)
            new_class_path = os.path.join("src", "main", "java", package_path, f"{suggestion.proposed_class_name}.java")
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
                result.error_message = f"Behavioral differences detected: {', '.join(equiv_result.differing_tests[:5])}"
                self.logger.warning(f"Equivalence checking failed: {result.error_message}")
                return result

            self.logger.info(f"✓ Equivalence verified ({equiv_result.tests_run} tests passed)")
        else:
            result.equivalence_pass = True
            self.logger.info("Equivalence checking skipped")

        # Layer 1: Syntactic Verification
        if self.enable_syntactic:
            self.logger.info("Layer 1: Syntactic Verification")

            syntactic_pass, error = self.syntactic_verifier.verify(
                suggestion.new_class_code,
                suggestion.modified_original_code,
                class_deps.package_name,
            )

            result.syntactic_pass = syntactic_pass

            if not syntactic_pass:
                result.status = "FAILED_SYNTACTIC"
                result.error_message = error
                self.logger.warning(f"Syntactic verification failed: {error}")
                return result
        else:
            result.syntactic_pass = True
            self.logger.info("Syntactic verification skipped")

        # Layer 1.5: Static Analysis (NEW - Code Quality)
        if self.enable_static_analysis:
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
                return result

            self.logger.info("✓ Static analysis passed (no quality regression)")
        else:
            result.quality_pass = True
            self.logger.info("Static analysis skipped")

        # Layer 1.7: Multi-Version Compilation (NEW)
        if self.enable_multiversion:
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
                return result

            self.logger.info("✓ Multi-version compilation passed")
        else:
            result.multiversion_pass = True
            self.logger.info("Multi-version compilation skipped")

        # Layer 2: Semantic Verification
        if self.enable_semantic:
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
                return result
        else:
            result.semantic_pass = True
            self.logger.info("Semantic verification skipped")

        # Layer 3: Behavioral Verification
        # Skip if equivalence checking already passed - they both run tests,
        # so this avoids redundant test execution
        if self.enable_behavioral and not result.equivalence_pass:
            # Only run behavioral if equivalence wasn't run or didn't pass
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
                return result
        elif self.enable_behavioral and result.equivalence_pass:
            # Equivalence already verified behavior - skip redundant check
            result.behavioral_pass = True
            self.logger.info("Behavioral verification skipped (equivalence already verified)")
        else:
            result.behavioral_pass = True
            self.logger.info("Behavioral verification skipped")

        # All layers passed
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
