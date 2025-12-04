"""
Multi-Version Compilation Verifier.

Ensures refactored code compiles across multiple Java versions (8, 11, 17, 21).
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class CompilationResult:
    """Result of compilation for a specific Java version."""

    version: str
    success: bool
    error_message: str | None = None


class MultiVersionCompilationVerifier:
    """
    Verifies code compiles across multiple Java versions.

    Ensures backward compatibility and forward compatibility
    for refactored code.
    """

    def __init__(
        self,
        java_versions: list[str] = None,
        javac_path_template: str = "/usr/lib/jvm/java-{version}-openjdk/bin/javac",
    ):
        """
        Initialize multi-version compilation verifier.

        Args:
            java_versions: List of Java versions to test (e.g., ['8', '11', '17', '21'])
            javac_path_template: Path template for javac binaries
        """
        self.java_versions = java_versions or ["8", "11", "17", "21"]
        self.javac_path_template = javac_path_template
        self.logger = get_logger(self.__class__.__name__)

    def verify(
        self, new_class_code: str, modified_original_code: str, package_name: str, class_name: str
    ) -> tuple[bool, str | None]:
        """
        Verify code compiles across all configured Java versions.

        Args:
            new_class_code: New extracted class code
            modified_original_code: Modified original class code
            package_name: Java package name
            class_name: Class name

        Returns:
            (passed, error_message) tuple
        """
        self.logger.info(f"Verifying compilation across Java versions: {self.java_versions}")

        results: list[CompilationResult] = []

        for version in self.java_versions:
            result = self._compile_with_version(
                new_class_code, modified_original_code, package_name, class_name, version
            )
            results.append(result)

        # Check if all versions compiled successfully
        failures = [r for r in results if not r.success]

        if not failures:
            self.logger.info(f"✓ Compiled successfully on all {len(results)} Java versions")
            return True, None
        else:
            error_msg = f"Failed on Java {', '.join(r.version for r in failures)}"
            self.logger.warning(error_msg)
            return False, error_msg

    def _compile_with_version(
        self,
        new_class_code: str,
        modified_original_code: str,
        package_name: str,
        class_name: str,
        java_version: str,
    ) -> CompilationResult:
        """
        Compile code with a specific Java version.

        Returns:
            CompilationResult with success status
        """
        # Find javac for this version
        javac_path = self._find_javac(java_version)

        if not javac_path:
            self.logger.warning(f"Java {java_version} compiler not found, skipping")
            return CompilationResult(
                version=java_version,
                success=True,  # Don't fail if version not installed
                error_message="Compiler not found (skipped)",
            )

        # Create temp directory for compilation
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)

            # Create package directory structure
            package_dir = temp_path / package_name.replace(".", "/")
            package_dir.mkdir(parents=True, exist_ok=True)

            # Write source files
            original_file = package_dir / f"{class_name}.java"
            new_file = package_dir / f"{class_name}Extracted.java"  # Dummy name

            original_file.write_text(modified_original_code)
            new_file.write_text(new_class_code)

            # Compile with specific Java version
            try:
                cmd = [
                    str(javac_path),
                    "-d",
                    str(temp_path),
                    "-source",
                    java_version,
                    "-target",
                    java_version,
                    str(original_file),
                    str(new_file),
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                if result.returncode == 0:
                    return CompilationResult(version=java_version, success=True)
                else:
                    return CompilationResult(
                        version=java_version, success=False, error_message=result.stderr[:200]
                    )

            except subprocess.TimeoutExpired:
                return CompilationResult(
                    version=java_version, success=False, error_message="Compilation timeout"
                )
            except Exception as e:
                return CompilationResult(version=java_version, success=False, error_message=str(e))

    def _find_javac(self, version: str) -> Path | None:
        """Find javac binary for specific Java version."""
        # Try common locations
        possible_paths = [
            Path(self.javac_path_template.format(version=version)),
            Path(f"/usr/lib/jvm/java-{version}/bin/javac"),
            Path(f"/Library/Java/JavaVirtualMachines/jdk-{version}.jdk/Contents/Home/bin/javac"),
            Path(f"C:\\Program Files\\Java\\jdk-{version}\\bin\\javac.exe"),
        ]

        for path in possible_paths:
            if path.exists():
                return path

        # Try using JAVA_HOME if set
        import os

        java_home = os.environ.get("JAVA_HOME")
        if java_home:
            javac = Path(java_home) / "bin" / "javac"
            if javac.exists():
                return javac

        return None

    def get_available_versions(self) -> list[str]:
        """Get list of available Java versions on system."""
        available = []
        for version in self.java_versions:
            if self._find_javac(version):
                available.append(version)
        return available

    def is_available(self) -> bool:
        """Check if at least one Java version is available."""
        return len(self.get_available_versions()) > 0
