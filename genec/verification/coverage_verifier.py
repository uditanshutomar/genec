"""
Coverage verification using JaCoCo.

Ensures that the extracted class is actually covered by the tests that passed.
This prevents "false positives" where tests pass simply because they don't touch the new code.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from genec.utils.logging_utils import get_logger


class CoverageVerifier:
    """Verifies test coverage of extracted classes using JaCoCo."""

    def __init__(self, min_coverage: float = 0.1):
        """
        Initialize coverage verifier.

        Args:
            min_coverage: Minimum required line coverage (0.0 to 1.0).
                          Default is low (10%) just to ensure *some* execution.
        """
        self.logger = get_logger(self.__class__.__name__)
        self.min_coverage = min_coverage

    def verify_coverage(
        self,
        repo_path: Path,
        class_name: str,
        build_system: str,
        report_path: Path | None = None,
    ) -> tuple[bool, float, str | None]:
        """
        Verify that the specified class has sufficient test coverage.

        Args:
            repo_path: Path to repository
            class_name: Name of the class to check (simple name)
            build_system: 'maven' or 'gradle'
            report_path: Optional path to JaCoCo XML report

        Returns:
            Tuple of (success, coverage_percentage, error_message)
        """
        if not report_path:
            report_path = self._find_jacoco_report(repo_path, build_system)

        if not report_path or not report_path.exists():
            return False, 0.0, "JaCoCo report not found. Ensure tests ran with coverage."

        try:
            coverage = self._parse_coverage(report_path, class_name)

            if coverage >= self.min_coverage:
                self.logger.info(f"Coverage check PASSED for {class_name}: {coverage:.1%}")
                return True, coverage, None
            else:
                msg = (
                    f"Coverage check FAILED for {class_name}: {coverage:.1%} "
                    f"(required: {self.min_coverage:.1%})"
                )
                self.logger.warning(msg)
                return False, coverage, msg

        except Exception as e:
            return False, 0.0, f"Failed to parse coverage report: {e}"

    def _find_jacoco_report(self, repo_path: Path, build_system: str) -> Path | None:
        """Find the JaCoCo XML report file."""
        # Common locations
        candidates = []
        if build_system == "maven":
            candidates = [
                repo_path / "target/site/jacoco/jacoco.xml",
                repo_path / "target/jacoco-report/jacoco.xml",
            ]
        elif build_system == "gradle":
            candidates = [
                repo_path / "build/reports/jacoco/test/jacocoTestReport.xml",
                repo_path / "build/reports/jacoco/report.xml",
            ]

        # Also search recursively if not found in standard locations
        for candidate in candidates:
            if candidate.exists():
                return candidate

        # Fallback: search
        try:
            found = list(repo_path.glob("**/jacoco.xml"))
            if found:
                return found[0]
        except Exception:
            pass

        return None

    def _parse_coverage(self, report_path: Path, class_name: str) -> float:
        """
        Parse JaCoCo XML report to get line coverage for a specific class.

        Args:
            report_path: Path to XML report
            class_name: Simple class name (e.g., "StringEncoder")

        Returns:
            Line coverage ratio (0.0 to 1.0)
        """
        tree = ET.parse(report_path)
        root = tree.getroot()

        # JaCoCo XML structure:
        # <package name="...">
        #   <class name="com/example/StringEncoder" ...>
        #     <counter type="LINE" missed="10" covered="40"/>

        # We search for class name suffix to handle packages
        # Class names in JaCoCo are like "com/example/MyClass"

        target_class = None

        # Iterate through all packages and classes
        for package in root.findall("package"):
            for cls in package.findall("class"):
                name = cls.get("name", "")
                # Check if this is the class we're looking for
                # Match "MyClass" or "Outer$Inner"
                if name.endswith(f"/{class_name}") or name == class_name:
                    target_class = cls
                    break
            if target_class:
                break

        if not target_class:
            self.logger.warning(f"Class {class_name} not found in coverage report")
            return 0.0

        # Get line coverage counter
        for counter in target_class.findall("counter"):
            if counter.get("type") == "LINE":
                missed = int(counter.get("missed", 0))
                covered = int(counter.get("covered", 0))
                total = missed + covered

                if total == 0:
                    return 0.0

                return covered / total

        return 0.0
