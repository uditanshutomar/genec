"""Multi-layer verification engine for refactoring suggestions."""

from dataclasses import dataclass
from typing import Optional

from genec.core.llm_interface import RefactoringSuggestion
from genec.core.dependency_analyzer import ClassDependencies
from genec.verification.syntactic_verifier import SyntacticVerifier
from genec.verification.semantic_verifier import SemanticVerifier
from genec.verification.behavioral_verifier import BehavioralVerifier
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class VerificationResult:
    """Result of multi-layer verification."""
    suggestion_id: int
    status: str  # PASSED_ALL, FAILED_SYNTACTIC, FAILED_SEMANTIC, FAILED_BEHAVIORAL
    syntactic_pass: bool = False
    semantic_pass: bool = False
    behavioral_pass: bool = False
    error_message: Optional[str] = None


class VerificationEngine:
    """Orchestrates multi-layer verification of refactoring suggestions."""

    def __init__(
        self,
        enable_syntactic: bool = True,
        enable_semantic: bool = True,
        enable_behavioral: bool = True,
        java_compiler: str = 'javac',
        maven_command: str = 'mvn',
        gradle_command: str = 'gradle',
        repo_path: Optional[str] = None
    ):
        """
        Initialize verification engine.

        Args:
            enable_syntactic: Enable syntactic verification
            enable_semantic: Enable semantic verification
            enable_behavioral: Enable behavioral verification
            java_compiler: Java compiler command
            maven_command: Maven command
            gradle_command: Gradle command
            repo_path: Path to repository root (for Maven/Gradle projects)
        """
        self.enable_syntactic = enable_syntactic
        self.enable_semantic = enable_semantic
        self.enable_behavioral = enable_behavioral

        self.syntactic_verifier = SyntacticVerifier(java_compiler, repo_path)
        self.semantic_verifier = SemanticVerifier()
        self.behavioral_verifier = BehavioralVerifier(maven_command, gradle_command)

        self.logger = get_logger(self.__class__.__name__)

    def verify_refactoring(
        self,
        suggestion: RefactoringSuggestion,
        original_code: str,
        original_class_file: str,
        repo_path: str,
        class_deps: ClassDependencies
    ) -> VerificationResult:
        """
        Perform multi-layer verification on a refactoring suggestion.

        Verification layers:
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

        result = VerificationResult(
            suggestion_id=suggestion.cluster_id,
            status='PENDING'
        )

        # Layer 1: Syntactic Verification
        if self.enable_syntactic:
            self.logger.info("Layer 1: Syntactic Verification")

            syntactic_pass, error = self.syntactic_verifier.verify(
                suggestion.new_class_code,
                suggestion.modified_original_code,
                class_deps.package_name
            )

            result.syntactic_pass = syntactic_pass

            if not syntactic_pass:
                result.status = 'FAILED_SYNTACTIC'
                result.error_message = error
                self.logger.warning(f"Syntactic verification failed: {error}")
                return result
        else:
            result.syntactic_pass = True
            self.logger.info("Syntactic verification skipped")

        # Layer 2: Semantic Verification
        if self.enable_semantic:
            self.logger.info("Layer 2: Semantic Verification")

            semantic_pass, error = self.semantic_verifier.verify(
                original_code,
                suggestion.new_class_code,
                suggestion.modified_original_code,
                suggestion.cluster,
                class_deps
            )

            result.semantic_pass = semantic_pass

            if not semantic_pass:
                result.status = 'FAILED_SEMANTIC'
                result.error_message = error
                self.logger.warning(f"Semantic verification failed: {error}")
                return result
        else:
            result.semantic_pass = True
            self.logger.info("Semantic verification skipped")

        # Layer 3: Behavioral Verification
        if self.enable_behavioral:
            self.logger.info("Layer 3: Behavioral Verification")

            behavioral_pass, error = self.behavioral_verifier.verify(
                original_class_file,
                suggestion.new_class_code,
                suggestion.modified_original_code,
                repo_path,
                class_deps.package_name
            )

            result.behavioral_pass = behavioral_pass

            if not behavioral_pass:
                result.status = 'FAILED_BEHAVIORAL'
                result.error_message = error
                self.logger.warning(f"Behavioral verification failed: {error}")
                return result
        else:
            result.behavioral_pass = True
            self.logger.info("Behavioral verification skipped")

        # All layers passed
        result.status = 'PASSED_ALL'
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
        status['java_compiler'] = self.syntactic_verifier.check_compiler_available()

        # Check build tools
        build_tools = self.behavioral_verifier.check_build_tools_available()
        status.update(build_tools)

        return status
