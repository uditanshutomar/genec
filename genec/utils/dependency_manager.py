"""
Dependency manager for GenEC.

Handles detection and automatic building of required external dependencies (JARs).
"""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class Dependency:
    """Represents an external dependency."""

    name: str
    jar_path: str
    source_path: str
    description: str


class DependencyManager:
    """Manages external dependencies for GenEC."""

    def __init__(self, project_root: Path):
        """
        Initialize dependency manager.

        Args:
            project_root: Root directory of the GenEC project
        """
        self.project_root = project_root
        self.dependencies = [
            Dependency(
                name="Eclipse JDT Wrapper",
                jar_path="genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar",
                source_path="genec-jdt-wrapper",
                description="Required for hybrid code generation (Stage 5)",
            ),
            Dependency(
                name="Spoon Wrapper",
                jar_path="genec-spoon-wrapper/target/genec-spoon-wrapper-1.0.0-jar-with-dependencies.jar",
                source_path="genec-spoon-wrapper",
                description="Required for high-accuracy static analysis (Stage 1)",
            ),
        ]

    def check_dependencies(self) -> dict[str, bool]:
        """
        Check status of all dependencies.

        Returns:
            Dictionary mapping dependency name to presence boolean
        """
        status = {}
        for dep in self.dependencies:
            jar_full_path = self.project_root / dep.jar_path
            status[dep.name] = jar_full_path.exists()
        return status

    def ensure_dependencies(self, auto_build: bool = True) -> bool:
        """
        Ensure all dependencies are available.

        Args:
            auto_build: Whether to attempt building missing dependencies

        Returns:
            True if all dependencies are available (or successfully built), False otherwise
        """
        missing = []
        for dep in self.dependencies:
            jar_full_path = self.project_root / dep.jar_path
            if not jar_full_path.exists():
                missing.append(dep)

        if not missing:
            logger.debug("All dependencies are present.")
            return True

        logger.info(f"Missing {len(missing)} dependencies: {', '.join(d.name for d in missing)}")

        if not auto_build:
            logger.warning("Auto-build is disabled. Some features may not work.")
            return False

        # Check for Maven
        if not shutil.which("mvn"):
            logger.error("Maven ('mvn') not found in PATH. Cannot build dependencies.")
            logger.error("Please install Maven or manually build the wrapper JARs.")
            return False

        success = True
        for dep in missing:
            logger.info(f"Building {dep.name}...")
            if not self._build_dependency(dep):
                logger.error(f"Failed to build {dep.name}")
                success = False
            else:
                logger.info(f"Successfully built {dep.name}")

        return success

    def _build_dependency(self, dep: Dependency) -> bool:
        """
        Build a single dependency using Maven.

        Args:
            dep: Dependency to build

        Returns:
            True if build succeeded
        """
        source_full_path = self.project_root / dep.source_path
        if not source_full_path.exists():
            logger.error(f"Source directory not found: {source_full_path}")
            return False

        try:
            # Run mvn package
            result = subprocess.run(
                ["mvn", "package", "-DskipTests"],
                cwd=str(source_full_path),
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                logger.error(f"Maven build failed for {dep.name}")
                logger.error(f"Stdout: {result.stdout}")
                logger.error(f"Stderr: {result.stderr}")
                return False

            # Verify JAR was created
            jar_full_path = self.project_root / dep.jar_path
            if not jar_full_path.exists():
                logger.error(f"Build succeeded but JAR not found at {jar_full_path}")
                return False

            return True

        except Exception as e:
            logger.error(f"Exception during build of {dep.name}: {e}")
            return False
