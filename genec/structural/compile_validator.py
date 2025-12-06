"""
Compile validation utilities for structural transformations.

Runs a configured build command (e.g., mvn compile) after structural scaffolding
is generated to ensure the repository remains in a compiling state.
"""

from __future__ import annotations

import shlex
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class CompileResult:
    """Represents the outcome of a compile validation run."""

    success: bool
    command: Sequence[str]
    stdout: str = ""
    stderr: str = ""
    error: str = ""

    def summary(self) -> str:
        base = "SUCCESS" if self.success else "FAILURE"
        cmd = " ".join(shlex.quote(part) for part in self.command)
        details = self.error or self.stderr
        details = details.strip()
        if details:
            return f"{base}: {cmd}\n{details}"
        return f"{base}: {cmd}"


class StructuralCompileValidator:
    """
    Runs a compile command inside the repository to validate structural changes.
    """

    def __init__(
        self,
        command: Sequence[str],
        timeout_seconds: int = 300,
    ):
        if not command:
            raise ValueError("Compile command must not be empty")
        self.command = list(command)
        self.timeout_seconds = timeout_seconds
        self.logger = get_logger(self.__class__.__name__)

    def run(self, repo_path: str) -> CompileResult:
        """Execute the compile command in the given repository."""
        repo_dir = Path(repo_path)
        if not repo_dir.exists():
            return CompileResult(
                success=False,
                command=self.command,
                error=f"Repository path not found: {repo_path}",
            )

        self.logger.info(
            "Running structural compile check: %s",
            " ".join(shlex.quote(part) for part in self.command),
        )

        try:
            completed = subprocess.run(
                self.command,
                cwd=str(repo_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            return CompileResult(
                success=completed.returncode == 0,
                command=self.command,
                stdout=completed.stdout or "",
                stderr=completed.stderr or "",
            )
        except subprocess.TimeoutExpired as exc:
            msg = f"Compile command timed out after {self.timeout_seconds}s: " f"{exc.cmd}"
            self.logger.error(msg)
            return CompileResult(
                success=False,
                command=self.command,
                stdout=exc.stdout.decode() if exc.stdout else "",
                stderr=exc.stderr.decode() if exc.stderr else "",
                error=msg,
            )
        except FileNotFoundError as exc:
            msg = f"Compile tool not found: {exc}"
            self.logger.error(msg)
            return CompileResult(
                success=False,
                command=self.command,
                error=msg,
            )
        except Exception as exc:  # pragma: no cover - unexpected edge cases
            msg = f"Compile command failed unexpectedly: {exc}"
            self.logger.error(msg)
            return CompileResult(
                success=False,
                command=self.command,
                error=msg,
            )
