import subprocess

import pytest

from genec.structural.compile_validator import StructuralCompileValidator


def test_compile_validator_success(tmp_path):
    command = ["python3", "-c", "import sys; sys.exit(0)"]
    validator = StructuralCompileValidator(command, timeout_seconds=5)
    result = validator.run(str(tmp_path))
    assert result.success
    assert "python3" in result.summary()


def test_compile_validator_failure(tmp_path):
    command = ["python3", "-c", "import sys; sys.exit(1)"]
    validator = StructuralCompileValidator(command, timeout_seconds=5)
    result = validator.run(str(tmp_path))
    assert not result.success
    assert "FAILURE" in result.summary()
