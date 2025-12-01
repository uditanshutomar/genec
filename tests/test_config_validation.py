"""
Tests for Pydantic configuration validation.

Verifies that the GenECConfig model properly validates configuration values
and provides clear error messages for invalid configurations.
"""

import pytest
from pathlib import Path

from genec.config import GenECConfig, load_config
from pydantic import ValidationError


class TestConfigValidation:
    """Test configuration validation with Pydantic."""

    def test_default_config(self):
        """Test that default configuration is valid."""
        config = GenECConfig()

        # Verify defaults are set
        assert config.fusion.alpha == 0.5
        assert config.clustering.min_cluster_size == 3
        assert config.llm.model == "claude-sonnet-4-20250514"
        assert config.verification.enable_syntactic is True

    def test_alpha_validation(self):
        """Test that fusion.alpha must be between 0 and 1."""
        # Valid values
        config = GenECConfig(fusion={"alpha": 0.0})
        assert config.fusion.alpha == 0.0

        config = GenECConfig(fusion={"alpha": 1.0})
        assert config.fusion.alpha == 1.0

        # Invalid value > 1
        with pytest.raises(ValidationError) as exc_info:
            GenECConfig(fusion={"alpha": 1.5})
        assert "less than or equal to 1" in str(exc_info.value)

        # Invalid value < 0
        with pytest.raises(ValidationError) as exc_info:
            GenECConfig(fusion={"alpha": -0.1})
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_cluster_size_validation(self):
        """Test that max_cluster_size >= min_cluster_size."""
        # Valid: max >= min
        config = GenECConfig(
            clustering={"min_cluster_size": 3, "max_cluster_size": 10}
        )
        assert config.clustering.min_cluster_size == 3
        assert config.clustering.max_cluster_size == 10

        # Invalid: max < min
        with pytest.raises(ValidationError) as exc_info:
            GenECConfig(
                clustering={"min_cluster_size": 10, "max_cluster_size": 3}
            )
        assert "max_cluster_size" in str(exc_info.value)
        assert "min_cluster_size" in str(exc_info.value)

    def test_clustering_algorithm_validation(self):
        """Test that only valid clustering algorithms are accepted."""
        # Valid algorithm
        config = GenECConfig(clustering={"algorithm": "louvain"})
        assert config.clustering.algorithm == "louvain"

        # Invalid algorithm
        with pytest.raises(ValidationError) as exc_info:
            GenECConfig(clustering={"algorithm": "invalid_algorithm"})
        assert "algorithm must be one of" in str(exc_info.value)

    def test_llm_provider_validation(self):
        """Test that only valid LLM providers are accepted."""
        # Valid provider
        config = GenECConfig(llm={"provider": "anthropic"})
        assert config.llm.provider == "anthropic"

        # Invalid provider
        with pytest.raises(ValidationError) as exc_info:
            GenECConfig(llm={"provider": "invalid_provider"})
        assert "provider must be one of" in str(exc_info.value)

    def test_code_generation_engine_validation(self):
        """Test that only valid code generation engines are accepted."""
        # Valid engine
        config = GenECConfig(code_generation={"engine": "eclipse_jdt"})
        assert config.code_generation.engine == "eclipse_jdt"

        # Invalid engine
        with pytest.raises(ValidationError) as exc_info:
            GenECConfig(code_generation={"engine": "invalid_engine"})
        assert "engine must be one of" in str(exc_info.value)

    def test_logging_level_validation(self):
        """Test that only valid logging levels are accepted."""
        # Valid level (case insensitive)
        config = GenECConfig(logging={"level": "debug"})
        assert config.logging.level == "DEBUG"

        config = GenECConfig(logging={"level": "INFO"})
        assert config.logging.level == "INFO"

        # Invalid level
        with pytest.raises(ValidationError) as exc_info:
            GenECConfig(logging={"level": "INVALID"})
        assert "level must be one of" in str(exc_info.value)

    def test_extra_fields_forbidden(self):
        """Test that extra unknown fields are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            GenECConfig(unknown_field="value")
        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_load_config_from_file(self, tmp_path: Path):
        """Test loading configuration from YAML file."""
        # Create a valid config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
fusion:
  alpha: 0.7
  edge_threshold: 0.05
clustering:
  min_cluster_size: 5
  max_cluster_size: 20
llm:
  model: claude-sonnet-4-20250514
  temperature: 0.5
""")

        config = load_config(str(config_file))

        assert config.fusion.alpha == 0.7
        assert config.fusion.edge_threshold == 0.05
        assert config.clustering.min_cluster_size == 5
        assert config.clustering.max_cluster_size == 20
        assert config.llm.temperature == 0.5

    def test_load_config_invalid_file(self, tmp_path: Path):
        """Test loading configuration with invalid values."""
        # Create an invalid config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
fusion:
  alpha: 2.0  # Invalid: > 1.0
""")

        with pytest.raises(ValueError) as exc_info:
            load_config(str(config_file))
        assert "Invalid configuration" in str(exc_info.value)

    def test_load_config_missing_file(self):
        """Test loading configuration from non-existent file."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yaml")

    def test_min_max_tokens_validation(self):
        """Test that max_tokens has reasonable bounds."""
        # Valid value
        config = GenECConfig(llm={"max_tokens": 4000})
        assert config.llm.max_tokens == 4000

        # Invalid: too small
        with pytest.raises(ValidationError) as exc_info:
            GenECConfig(llm={"max_tokens": 0})
        assert "greater than or equal to 1" in str(exc_info.value)

        # Invalid: too large
        with pytest.raises(ValidationError) as exc_info:
            GenECConfig(llm={"max_tokens": 300000})
        assert "less than or equal to 200000" in str(exc_info.value)

    def test_temperature_validation(self):
        """Test that temperature is between 0 and 1."""
        # Valid values
        config = GenECConfig(llm={"temperature": 0.0})
        assert config.llm.temperature == 0.0

        config = GenECConfig(llm={"temperature": 1.0})
        assert config.llm.temperature == 1.0

        # Invalid: > 1
        with pytest.raises(ValidationError) as exc_info:
            GenECConfig(llm={"temperature": 1.5})
        assert "less than or equal to 1" in str(exc_info.value)

        # Invalid: < 0
        with pytest.raises(ValidationError) as exc_info:
            GenECConfig(llm={"temperature": -0.1})
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_partial_config(self):
        """Test that partial configuration merges with defaults."""
        # Only specify some fields
        config = GenECConfig(
            fusion={"alpha": 0.8}
            # edge_threshold should use default
        )

        assert config.fusion.alpha == 0.8
        assert config.fusion.edge_threshold == 0.1  # default value
        assert config.clustering.min_cluster_size == 3  # default value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
