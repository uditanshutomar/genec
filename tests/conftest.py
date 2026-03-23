"""Pytest fixtures for GenEC tests."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_java_file(temp_dir):
    """Create a sample Java file for testing."""
    java_content = '''
package com.example;

public class SampleClass {
    private int field1;
    private String field2;

    public void method1() {
        field1 = 10;
    }

    public void method2() {
        field2 = "test";
    }

    public void method3() {
        method1();
        method2();
    }
}
'''
    java_file = temp_dir / "SampleClass.java"
    java_file.write_text(java_content)
    return java_file


@pytest.fixture
def sample_git_repo(temp_dir):
    """Create a sample git repository for testing."""
    import subprocess

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=temp_dir, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=temp_dir,
        capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=temp_dir,
        capture_output=True
    )

    # Create initial commit
    (temp_dir / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=temp_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_dir,
        capture_output=True
    )

    return temp_dir


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for LLM tests."""
    with patch("genec.core.llm_interface.Anthropic") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance

        # Mock response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="TestClassName")]
        mock_instance.messages.create.return_value = mock_response

        yield mock_instance


@pytest.fixture
def sample_config():
    """Return a sample GenEC configuration dict."""
    return {
        "clustering": {
            "algorithm": "louvain",
            "min_cluster_size": 3,
            "max_cluster_size": 30,
            "min_cohesion": 0.35,
            "resolution": 1.0,
        },
        "llm": {
            "model": "claude-sonnet-4-20250514",
            "temperature": 0.2,
            "max_tokens": 4096,
        },
        "verification": {
            "enable_syntactic": True,
            "enable_semantic": True,
            "enable_behavioral": False,
        },
        "code_generation": {
            "use_jdt": True,
        },
    }


@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment variables after each test."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)
