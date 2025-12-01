"""
Pydantic models for GenEC configuration.

Provides type-safe, validated configuration with clear error messages
and automatic validation of all configuration values.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class FusionConfig(BaseModel):
    """Configuration for graph fusion."""

    alpha: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight for static dependencies (0-1). Higher values favor static over evolutionary coupling.",
    )
    edge_threshold: float = Field(
        default=0.1, ge=0.0, le=1.0, description="Minimum edge weight to keep in fused graph (0-1)."
    )


class EvolutionConfig(BaseModel):
    """Configuration for evolutionary coupling analysis."""

    window_months: int = Field(
        default=36, ge=1, description="Number of months of history to analyze."
    )
    min_commits: int = Field(
        default=1, ge=1, description="Minimum commits required for coupling analysis."
    )


class ClusteringConfig(BaseModel):
    """Configuration for cluster detection."""

    algorithm: str = Field(default="louvain", description="Clustering algorithm to use.")
    min_cluster_size: int = Field(
        default=3, ge=2, description="Minimum number of members in a cluster."
    )
    max_cluster_size: int = Field(
        default=50, ge=2, description="Maximum number of members in a cluster."
    )
    min_cohesion: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Minimum cohesion score for a cluster (0-1)."
    )
    resolution: float = Field(
        default=0.8,
        ge=0.0,
        description="Resolution parameter for Louvain algorithm. Higher = more clusters.",
    )

    @field_validator("algorithm")
    @classmethod
    def validate_algorithm(cls, v: str) -> str:
        """Validate clustering algorithm."""
        allowed = {"louvain", "leiden", "spectral"}
        if v not in allowed:
            raise ValueError(f"algorithm must be one of {allowed}, got: {v}")
        return v

    @model_validator(mode="after")
    def validate_cluster_sizes(self) -> "ClusteringConfig":
        """Validate that max_cluster_size >= min_cluster_size."""
        if self.max_cluster_size < self.min_cluster_size:
            raise ValueError(
                f"max_cluster_size ({self.max_cluster_size}) must be >= "
                f"min_cluster_size ({self.min_cluster_size})"
            )
        return self


class ChunkingConfig(BaseModel):
    """Configuration for code chunking."""

    enabled: bool = Field(default=True, description="Enable intelligent code chunking for LLM.")
    include_imports: bool = Field(default=True, description="Include import statements in chunks.")
    include_unused_fields_comment: bool = Field(
        default=True, description="Include comment about unused fields."
    )


class LLMConfig(BaseModel):
    """Configuration for LLM interface."""

    provider: str = Field(default="anthropic", description="LLM provider to use.")
    model: str = Field(default="claude-sonnet-4-20250514", description="Model identifier.")
    max_tokens: int = Field(
        default=4000, ge=1, le=200000, description="Maximum tokens in LLM response."
    )
    temperature: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Temperature for LLM sampling (0-1)."
    )
    timeout: int = Field(default=120, ge=1, description="Timeout for LLM requests in seconds.")
    api_key: str | None = Field(
        default=None,
        description="API key for LLM provider. If not set, uses ANTHROPIC_API_KEY env var.",
    )

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate LLM provider."""
        allowed = {"anthropic", "openai"}
        if v not in allowed:
            raise ValueError(f"provider must be one of {allowed}, got: {v}")
        return v


class CodeGenerationConfig(BaseModel):
    """Configuration for code generation."""

    engine: str = Field(default="eclipse_jdt", description="Code generation engine to use.")
    jdt_wrapper_jar: str = Field(
        default="genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar",
        description="Path to Eclipse JDT wrapper JAR file.",
    )
    timeout: int = Field(default=60, ge=1, description="Timeout for code generation in seconds.")

    @field_validator("engine")
    @classmethod
    def validate_engine(cls, v: str) -> str:
        """Validate code generation engine."""
        allowed = {"eclipse_jdt", "template"}
        if v not in allowed:
            raise ValueError(f"engine must be one of {allowed}, got: {v}")
        return v


class VerificationConfig(BaseModel):
    """Configuration for refactoring verification."""

    enable_syntactic: bool = Field(
        default=True, description="Enable syntactic verification (parsing)."
    )
    enable_semantic: bool = Field(
        default=True, description="Enable semantic verification (compilation)."
    )
    enable_behavioral: bool = Field(
        default=True, description="Enable behavioral verification (tests)."
    )
    enable_extraction_validation: bool = Field(
        default=True, description="Validate extraction completeness."
    )
    suggest_pattern_transformations: bool = Field(
        default=True, description="Suggest pattern transformations for failing verifications."
    )
    java_compiler: str = Field(default="javac", description="Java compiler command.")
    maven_command: str = Field(default="mvn", description="Maven command.")
    gradle_command: str = Field(default="./gradlew", description="Gradle wrapper command.")
    max_workers: int = Field(
        default=4, ge=1, description="Maximum parallel workers for verification."
    )
    # Selective testing configuration
    selective_testing_enabled: bool = Field(
        default=True, description="Enable selective testing to run only relevant tests."
    )
    selective_testing_min_confidence: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for selective testing (0.0-1.0).",
    )
    selective_testing_min_tests: int = Field(
        default=1, ge=1, description="Minimum number of tests required for selective testing."
    )
    selective_testing_max_tests: int = Field(
        default=100,
        ge=1,
        description="Maximum number of tests for selective testing before using fallback.",
    )
    test_timeout_seconds: int = Field(
        default=1800, ge=1, description="Timeout for test execution in seconds."
    )


class StructuralTransformsConfig(BaseModel):
    """Configuration for structural transformations."""

    enabled: bool = Field(default=False, description="Enable structural transformations.")
    require_confirmation: bool = Field(
        default=True, description="Require user confirmation before applying."
    )
    compile_check: bool = Field(
        default=True, description="Verify compilation after transformation."
    )
    max_methods: int = Field(
        default=40, ge=1, description="Maximum methods in a class to consider."
    )
    max_fields: int = Field(default=20, ge=1, description="Maximum fields in a class to consider.")
    output_dir: str = Field(
        default="data/outputs/structural_plans",
        description="Output directory for structural plans.",
    )
    compile_command: list[str] = Field(
        default=["./gradlew", ":core:spring-boot:compileJava"],
        description="Command to compile the project.",
    )
    compile_timeout_seconds: int = Field(
        default=300, ge=1, description="Timeout for compilation in seconds."
    )


class RefactoringApplicationConfig(BaseModel):
    """Configuration for refactoring application."""

    enabled: bool = Field(default=False, description="Enable refactoring application stage.")
    auto_apply: bool = Field(
        default=False, description="Automatically apply verified refactorings."
    )
    create_backups: bool = Field(default=True, description="Create backups before modifying files.")
    backup_dir: str = Field(default=".genec_backups", description="Directory for backups.")
    dry_run: bool = Field(
        default=True, description="If true, only simulate (don't actually write files)."
    )


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    level: str = Field(default="INFO", description="Logging level.")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format.",
    )
    file: str | None = Field(default=None, description="Optional log file path.")

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate logging level."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"level must be one of {allowed}, got: {v}")
        return v_upper


class CacheConfig(BaseModel):
    """Configuration for caching."""

    enable: bool = Field(default=True, description="Enable caching of expensive operations.")
    directory: str = Field(default="data/outputs/cache", description="Cache directory path.")
    ttl_days: int = Field(default=7, ge=1, description="Time-to-live for cache entries in days.")


class GenECConfig(BaseModel):
    """Main GenEC configuration."""

    fusion: FusionConfig = Field(default_factory=FusionConfig)
    evolution: EvolutionConfig = Field(default_factory=EvolutionConfig)
    clustering: ClusteringConfig = Field(default_factory=ClusteringConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    code_generation: CodeGenerationConfig = Field(default_factory=CodeGenerationConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    structural_transforms: StructuralTransformsConfig = Field(
        default_factory=StructuralTransformsConfig
    )
    refactoring_application: RefactoringApplicationConfig = Field(
        default_factory=RefactoringApplicationConfig
    )
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)

    model_config = {
        "extra": "forbid",  # Raise error on unknown fields
        "validate_assignment": True,  # Validate on attribute assignment
    }


def load_config(config_file: str = "config/config.yaml") -> GenECConfig:
    """
    Load and validate GenEC configuration from YAML file.

    Args:
        config_file: Path to YAML configuration file

    Returns:
        Validated GenECConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If configuration is invalid
        yaml.YAMLError: If YAML parsing fails
    """
    config_path = Path(config_file)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    try:
        with open(config_path) as f:
            config_dict = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML configuration: {e}")

    if config_dict is None:
        config_dict = {}

    try:
        return GenECConfig(**config_dict)
    except Exception as e:
        raise ValueError(f"Invalid configuration: {e}")


def save_config(config: GenECConfig, config_file: str = "config/config.yaml") -> None:
    """
    Save GenEC configuration to YAML file.

    Args:
        config: GenECConfig instance to save
        config_file: Path to YAML configuration file
    """
    config_path = Path(config_file)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict and remove None values for cleaner output
    config_dict = config.model_dump(exclude_none=True)

    with open(config_path, "w") as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
