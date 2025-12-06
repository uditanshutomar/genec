"""
Spoon-based Java parser for production-grade dependency analysis.

This parser wraps the Spoon Java metaprogramming library to provide
more accurate and comprehensive Java source code analysis than javalang.

Architecture:
    GenEC (Python) → Spoon Wrapper (Java) → Spoon Library → Analysis Results

Benefits over javalang:
    - 100% Java language support (up to Java 20+)
    - Handles all language features: generics, lambdas, annotations, etc.
    - Battle-tested on thousands of projects
    - Maintained by INRIA research lab
"""

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from genec.utils.logging_utils import get_logger


@dataclass
class SpoonAnalysisResult:
    """Result from Spoon analysis."""

    class_name: str
    package_name: str
    methods: list[dict]
    constructors: list[dict]
    fields: list[dict]
    method_calls: dict[str, list[str]]
    field_accesses: dict[str, list[str]]


class SpoonParserError(Exception):
    """Raised when Spoon parsing fails."""

    pass


class SpoonParser:
    """
    Production-grade Java parser using Spoon library.

    Spoon is a metaprogramming library by INRIA that provides comprehensive
    Java source code analysis with full language support.
    """

    def __init__(self, spoon_wrapper_jar: str | None = None, timeout: int = 60):
        """
        Initialize Spoon parser.

        Args:
            spoon_wrapper_jar: Path to genec-spoon-wrapper JAR file.
                             If None, looks in default location.
            timeout: Timeout for Spoon process in seconds
        """
        self.logger = get_logger(self.__class__.__name__)
        self.timeout = timeout

        # Find Spoon wrapper JAR
        if spoon_wrapper_jar is None:
            spoon_wrapper_jar = self._find_spoon_wrapper()

        if not os.path.exists(spoon_wrapper_jar):
            raise FileNotFoundError(
                f"Spoon wrapper JAR not found: {spoon_wrapper_jar}\n"
                f"Please build it with: cd genec-spoon-wrapper && mvn package"
            )

        self.spoon_wrapper_jar = spoon_wrapper_jar
        self.logger.info(f"Using Spoon wrapper: {spoon_wrapper_jar}")

    def _find_spoon_wrapper(self) -> str:
        """Find Spoon wrapper JAR in default locations."""
        project_root = Path(__file__).parent.parent.parent

        possible_locations = [
            # Relative paths (legacy)
            "genec-spoon-wrapper/target/genec-spoon-wrapper-1.0.0-jar-with-dependencies.jar",
            "lib/genec-spoon-wrapper.jar",
            # Absolute paths relative to project root
            str(
                project_root
                / "genec-spoon-wrapper/target/genec-spoon-wrapper-1.0.0-jar-with-dependencies.jar"
            ),
            str(project_root / "lib/genec-spoon-wrapper.jar"),
        ]

        for location in possible_locations:
            if os.path.exists(location):
                return location

        # Default to expected Maven output location (absolute)
        return str(
            project_root
            / "genec-spoon-wrapper/target/genec-spoon-wrapper-1.0.0-jar-with-dependencies.jar"
        )

    def analyze_class(self, class_file: str) -> SpoonAnalysisResult | None:
        """
        Analyze a Java class file using Spoon.

        Args:
            class_file: Path to Java source file

        Returns:
            SpoonAnalysisResult or None if analysis fails

        Raises:
            SpoonParserError: If Spoon analysis fails
        """
        self.logger.info(f"Analyzing class with Spoon: {class_file}")

        # Validate input
        file_path = Path(class_file)
        if not file_path.exists():
            raise SpoonParserError(f"File does not exist: {class_file}")

        if not file_path.is_file():
            raise SpoonParserError(f"Path is not a file: {class_file}")

        # Build analysis specification
        spec = {"classFile": str(file_path.absolute()), "analysisMode": "dependency"}

        # Call Spoon wrapper
        result = self._call_spoon_wrapper(spec)

        # Parse result
        if not result.get("success", False):
            raise SpoonParserError(
                f"Spoon analysis failed: {result.get('message', 'Unknown error')}"
            )

        # Convert to SpoonAnalysisResult
        return SpoonAnalysisResult(
            class_name=result.get("className", ""),
            package_name=result.get("packageName", ""),
            methods=result.get("methods", []),
            constructors=result.get("constructors", []),
            fields=result.get("fields", []),
            method_calls=result.get("methodCalls", {}),
            field_accesses=result.get("fieldAccesses", {}),
        )

    def _call_spoon_wrapper(self, spec: dict) -> dict:
        """
        Call Spoon wrapper via subprocess.

        Args:
            spec: Analysis specification

        Returns:
            Result dictionary from Spoon wrapper

        Raises:
            SpoonParserError: If subprocess call fails
        """
        spec_json = json.dumps(spec)

        try:
            # Execute Spoon wrapper
            result = subprocess.run(
                ["java", "-jar", self.spoon_wrapper_jar, "--spec", spec_json],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            # Parse stdout (JSON result)
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                # Parse stderr (error JSON)
                try:
                    error_result = json.loads(result.stderr)
                    return error_result
                except json.JSONDecodeError:
                    raise SpoonParserError(
                        f"Spoon process failed with exit code {result.returncode}\n"
                        f"stdout: {result.stdout}\n"
                        f"stderr: {result.stderr}"
                    )

        except subprocess.TimeoutExpired:
            raise SpoonParserError(f"Spoon process timed out after {self.timeout} seconds")
        except FileNotFoundError:
            raise SpoonParserError("Java runtime not found. Please ensure Java 11+ is installed.")
        except Exception as e:
            raise SpoonParserError(f"Error calling Spoon wrapper: {str(e)}")

    def is_available(self) -> bool:
        """
        Check if Spoon wrapper is available.

        Returns:
            True if Spoon wrapper JAR exists and Java is available
        """
        if not os.path.exists(self.spoon_wrapper_jar):
            return False

        try:
            # Check if Java is available
            result = subprocess.run(["java", "-version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
