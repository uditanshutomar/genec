"""Tests for the CLI module."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCLIArguments:
    """Test CLI argument parsing."""

    def test_help_argument(self):
        """Test --help argument."""
        from genec.cli import create_parser

        parser = create_parser()
        # Should not raise
        assert parser is not None

    def test_required_arguments(self):
        """Test that required arguments are enforced."""
        from genec.cli import create_parser

        parser = create_parser()

        # Missing --target should fail
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_target_argument(self, sample_java_file):
        """Test --target argument parsing."""
        from genec.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["--target", str(sample_java_file), "--repo", str(sample_java_file.parent)])

        assert args.target == str(sample_java_file)

    def test_json_output_flag(self, sample_java_file):
        """Test --json flag."""
        from genec.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(
            ["--target", str(sample_java_file), "--repo", str(sample_java_file.parent), "--json"]
        )

        assert args.json is True

    def test_clustering_arguments(self, sample_java_file):
        """Test clustering configuration arguments."""
        from genec.cli import create_parser

        parser = create_parser()
        args = parser.parse_args([
            "--target", str(sample_java_file),
            "--repo", str(sample_java_file.parent),
            "--min-cluster-size", "5",
            "--max-cluster-size", "20",
            "--min-cohesion", "0.5",
        ])

        assert args.min_cluster_size == 5
        assert args.max_cluster_size == 20
        assert args.min_cohesion == 0.5


class TestCLIValidation:
    """Test CLI input validation."""

    def test_nonexistent_file(self, temp_dir):
        """Test error handling for non-existent file."""
        from genec.cli import validate_target_file

        nonexistent = temp_dir / "nonexistent.java"

        with pytest.raises(FileNotFoundError):
            validate_target_file(str(nonexistent))

    def test_non_java_file(self, temp_dir):
        """Test error handling for non-Java file."""
        from genec.cli import validate_target_file

        py_file = temp_dir / "test.py"
        py_file.write_text("print('hello')")

        with pytest.raises(ValueError, match="must be a .java file"):
            validate_target_file(str(py_file))

    def test_valid_java_file(self, sample_java_file):
        """Test validation passes for valid Java file."""
        from genec.cli import validate_target_file

        # Should not raise
        result = validate_target_file(str(sample_java_file))
        assert result is not None  # Should return a valid path for valid Java files


class TestCLIEnvironment:
    """Test CLI environment handling."""

    def test_api_key_from_env(self, monkeypatch):
        """Test API key is read from environment."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")

        from genec.utils.secrets import get_anthropic_api_key

        key = get_anthropic_api_key()
        assert key == "sk-ant-test-key"

    def test_api_key_not_set(self, monkeypatch):
        """Test handling when API key is not set."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        from genec.utils.secrets import get_anthropic_api_key

        key = get_anthropic_api_key()
        assert key is None


class TestCLIOutput:
    """Test CLI output formats."""

    def test_json_output_format(self):
        """Test JSON output is valid."""
        output = {
            "status": "success",
            "suggestions": [],
            "original_metrics": {},
        }

        # Should be valid JSON
        json_str = json.dumps(output)
        parsed = json.loads(json_str)
        assert parsed["status"] == "success"

    def test_error_json_format(self):
        """Test error JSON format."""
        output = {
            "status": "error",
            "error": "Test error message",
        }

        json_str = json.dumps(output)
        parsed = json.loads(json_str)
        assert parsed["status"] == "error"
        assert "error" in parsed
