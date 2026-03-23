import pytest
from genec.config.models import (
    ClusteringConfig, FusionConfig, LLMConfig, GenECConfig
)


class TestClusteringConfigValidation:
    def test_rejects_invalid_algorithm(self):
        with pytest.raises(ValueError, match="algorithm must be one of"):
            ClusteringConfig(algorithm="invalid")

    def test_rejects_max_less_than_min(self):
        with pytest.raises(ValueError, match="max_cluster_size"):
            ClusteringConfig(min_cluster_size=10, max_cluster_size=5)

    def test_accepts_valid_config(self):
        c = ClusteringConfig(algorithm="leiden", min_cluster_size=3, max_cluster_size=30)
        assert c.algorithm == "leiden"


class TestFusionConfigValidation:
    def test_alpha_bounds(self):
        with pytest.raises(ValueError):
            FusionConfig(alpha=1.5)

    def test_edge_threshold_bounds(self):
        with pytest.raises(ValueError):
            FusionConfig(edge_threshold=-0.1)


class TestLLMConfigValidation:
    def test_rejects_invalid_provider(self):
        with pytest.raises(ValueError, match="provider must be one of"):
            LLMConfig(provider="invalid")

    def test_accepts_anthropic(self):
        c = LLMConfig(provider="anthropic")
        assert c.provider == "anthropic"


class TestFusionDefaults:
    def test_alpha_default_matches_config(self):
        c = FusionConfig()
        assert c.alpha == 0.6

    def test_edge_threshold_default(self):
        c = FusionConfig()
        assert c.edge_threshold == 0.05


class TestClusteringDefaults:
    def test_algorithm_default_is_leiden(self):
        c = ClusteringConfig()
        assert c.algorithm == "leiden"
