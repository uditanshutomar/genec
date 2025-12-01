"""Custom exceptions for GenEC."""


class GenECError(Exception):
    """Base exception for all GenEC errors."""

    pass


# Configuration Errors
class ConfigurationError(GenECError):
    """Raised when configuration is invalid or cannot be loaded."""

    pass


# Analysis Errors
class DependencyAnalysisError(GenECError):
    """Raised when dependency analysis fails."""

    pass


class ClusteringError(GenECError):
    """Raised when clustering fails."""

    pass


# Code Generation Errors
class CodeGenerationError(GenECError):
    """Raised when code generation fails."""

    pass


class JDTError(CodeGenerationError):
    """Raised when Eclipse JDT operations fail."""

    pass


# Verification Errors
class VerificationError(GenECError):
    """Raised when verification fails."""

    pass


class SyntacticVerificationError(VerificationError):
    """Raised when syntactic verification fails."""

    pass


class SemanticVerificationError(VerificationError):
    """Raised when semantic verification fails."""

    pass


class TestVerificationError(VerificationError):
    """Raised when test verification fails."""

    pass


# Refactoring Errors
class RefactoringError(GenECError):
    """Raised when refactoring application fails."""

    pass


class RefactoringApplicationError(RefactoringError):
    """Raised when applying a refactoring fails."""

    pass


# LLM Errors
class LLMError(GenECError):
    """Base class for LLM-related errors."""

    pass


class LLMServiceUnavailable(LLMError):
    """Raised when LLM service is unavailable."""

    pass


class LLMRequestFailed(LLMError):
    """Raised when LLM request fails."""

    pass


# Git/Evolution Errors
class GitError(GenECError):
    """Raised when Git operations fail."""

    pass


class EvolutionaryMiningError(GitError):
    """Raised when evolutionary coupling mining fails."""

    pass


# Input/Output Errors
class InputValidationError(GenECError):
    """Raised when input validation fails."""

    pass


class FileOperationError(GenECError):
    """Raised when file operations fail."""

    pass
