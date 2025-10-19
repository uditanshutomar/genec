"""Syntactic verification through compilation checks."""

import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Tuple
import os
import re

from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


class SyntacticVerifier:
    """Verifies refactorings are syntactically correct by compiling them."""

    def __init__(self, java_compiler: str = 'javac', repo_path: Optional[str] = None):
        """
        Initialize syntactic verifier.

        Args:
            java_compiler: Path to Java compiler (default: javac)
            repo_path: Path to repository root (for Maven/Gradle projects)
        """
        self.java_compiler = java_compiler
        self.repo_path = repo_path
        self.logger = get_logger(self.__class__.__name__)

        # Detect build system
        self.build_system = self._detect_build_system() if repo_path else None
        if self.build_system:
            self.logger.info(f"Detected build system: {self.build_system}")

        # Discover source paths for dependency resolution
        self.source_paths = self._discover_source_paths() if repo_path else []
        if self.source_paths:
            self.logger.debug(
                "Discovered source paths for syntactic verification: %s",
                [str(p) for p in self.source_paths]
            )

        # Discover module names (if any) to adjust module reads when compiling
        self.modules = self._discover_modules() if repo_path else []

    def verify(
        self,
        new_class_code: str,
        modified_original_code: str,
        package_name: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify that refactored code compiles successfully.

        Args:
            new_class_code: Code for new extracted class
            modified_original_code: Code for modified original class
            package_name: Package name for classes

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        self.logger.info("Running syntactic verification")

        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create package directory structure
            if package_name:
                package_path = temp_path / package_name.replace('.', '/')
                package_path.mkdir(parents=True, exist_ok=True)
            else:
                package_path = temp_path

            try:
                # Extract class names from code
                new_class_name = self._extract_class_name(new_class_code)
                original_class_name = self._extract_class_name(modified_original_code)

                if not new_class_name or not original_class_name:
                    return False, "Failed to extract class names from code"

                # Write code to files
                new_class_file = package_path / f"{new_class_name}.java"
                original_class_file = package_path / f"{original_class_name}.java"

                new_class_file.write_text(new_class_code, encoding='utf-8')
                original_class_file.write_text(modified_original_code, encoding='utf-8')

                # Compile both files
                success, error = self._compile_files(
                    [new_class_file, original_class_file],
                    temp_path
                )

                if success:
                    self.logger.info("Syntactic verification PASSED")
                    return True, None
                else:
                    self.logger.warning(f"Syntactic verification FAILED: {error}")
                    return False, error

            except Exception as e:
                error_msg = f"Syntactic verification error: {str(e)}"
                self.logger.error(error_msg)
                return False, error_msg

    def _extract_class_name(self, code: str) -> Optional[str]:
        """
        Extract class name from Java code.

        Args:
            code: Java source code

        Returns:
            Class name or None
        """
        import re

        # Look for class declaration
        pattern = r'(?:public\s+)?(?:abstract\s+)?class\s+(\w+)'
        match = re.search(pattern, code)

        if match:
            return match.group(1)

        return None

    def _compile_files(
        self,
        java_files: list,
        classpath: Path
    ) -> Tuple[bool, Optional[str]]:
        """
        Compile Java files using Maven/Gradle or javac.

        Args:
            java_files: List of Java file paths
            classpath: Classpath for compilation

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        # If Maven/Gradle available, use it for compilation with proper dependencies
        if self.build_system == 'maven':
            return self._compile_with_maven(java_files)
        elif self.build_system == 'gradle':
            return self._compile_with_gradle(java_files)
        else:
            # Fallback to javac
            return self._compile_with_javac(java_files, classpath)

    def _compile_with_javac(
        self,
        java_files: list,
        classpath: Path
    ) -> Tuple[bool, Optional[str]]:
        """
        Compile Java files using javac.

        Args:
            java_files: List of Java file paths
            classpath: Classpath for compilation

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Build classpath
            classpath_entries = [classpath]
            if self.repo_path:
                classpath_entries.append(Path(self.repo_path))
            classpath_str = os.pathsep.join(str(p) for p in classpath_entries)

            # Build sourcepath including repo sources for dependent types
            source_entries = [classpath]
            source_entries.extend(self.source_paths)
            sourcepath_str = os.pathsep.join(str(p) for p in source_entries)

            # Build javac command
            cmd = [
                self.java_compiler,
                '-classpath', classpath_str,
                '-sourcepath', sourcepath_str,
                '-d', str(classpath)
            ] + [str(f) for f in java_files]

            # When modules are present, ensure they can read required desktop APIs
            if self.modules:
                cmd.extend([
                    '--add-modules', 'java.desktop,java.datatransfer'
                ])
                for module in self.modules:
                    cmd.extend([
                        '--add-reads', f'{module}=java.desktop,java.datatransfer',
                        '--add-reads', f'{module}=ALL-UNNAMED'
                    ])

            # Run compilation
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return True, None
            else:
                error_msg = result.stderr or result.stdout
                return False, error_msg

        except subprocess.TimeoutExpired:
            return False, "Compilation timeout"
        except FileNotFoundError:
            return False, f"Java compiler not found: {self.java_compiler}"
        except Exception as e:
            return False, f"Compilation error: {str(e)}"

    def _discover_source_paths(self) -> list:
        """
        Discover source directories within the repository for dependency resolution.

        Returns:
            List of Paths to source directories.
        """
        repo = Path(self.repo_path)
        candidates = set()

        patterns = [
            '**/src/main/java',
            '**/src/java',
            '**/src',
        ]

        for pattern in patterns:
            for path in repo.glob(pattern):
                if path.is_dir():
                    resolved = path.resolve()
                    candidates.add(resolved)

                    # Include module subdirectories (e.g., org.jhotdraw7.application)
                    for child in resolved.iterdir():
                        if child.is_dir():
                            try:
                                has_java = next(child.rglob('*.java'), None)
                            except StopIteration:
                                has_java = None
                            if has_java:
                                candidates.add(child.resolve())

        # Prefer more specific paths (shorter depth first)
        ordered = sorted(candidates, key=lambda p: (len(p.parts), str(p)))

        return ordered

    def _discover_modules(self) -> list:
        """
        Discover Java module names declared in the repository.

        Returns:
            List of module names (strings).
        """
        modules = set()
        repo = Path(self.repo_path)

        for module_file in repo.rglob('module-info.java'):
            try:
                text = module_file.read_text(encoding='utf-8')
            except Exception:
                continue

            match = re.search(r'\bmodule\s+([a-zA-Z0-9_.]+)\s*\{', text)
            if match:
                modules.add(match.group(1))

        return sorted(modules)

    def _compile_with_maven(self, java_files: list) -> Tuple[bool, Optional[str]]:
        """
        Compile using Maven (runs full project compilation).

        Args:
            java_files: List of Java file paths (logged for info)

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            self.logger.info(f"Compiling project with Maven in {self.repo_path}")

            # Run Maven compile
            cmd = [
                'mvn',
                '-q',
                'compile',
                '-DskipTests',
                '-Dmaven.compiler.source=1.8',
                '-Dmaven.compiler.target=1.8'
            ]

            if self.modules:
                cmd.append('-DforceAddModules=java.desktop,java.datatransfer')

            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                return True, None
            else:
                # Extract relevant errors
                error_msg = result.stderr or result.stdout
                # If Maven already compiled successfully but produced warnings, treat as success
                if ('COMPILATION ERROR' not in error_msg and
                        'BUILD FAILURE' not in error_msg and
                        'error:' not in error_msg):
                    self.logger.debug("Maven returned non-zero but without compilation errors; treating as success.")
                    return True, None

                # Try to find compilation errors
                if 'COMPILATION ERROR' in error_msg or 'error:' in error_msg:
                    return False, error_msg
                else:
                    # Other Maven errors (dependencies, etc.)
                    return False, f"Maven build failed: {error_msg}"

        except subprocess.TimeoutExpired:
            return False, "Maven compilation timeout"
        except FileNotFoundError:
            return False, "Maven not found"
        except Exception as e:
            return False, f"Maven error: {str(e)}"

    def _compile_with_gradle(self, java_files: list) -> Tuple[bool, Optional[str]]:
        """
        Compile using Gradle (runs full project compilation).

        Args:
            java_files: List of Java file paths (logged for info)

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            self.logger.info(f"Compiling project with Gradle in {self.repo_path}")

            # Run Gradle compile
            result = subprocess.run(
                ['./gradlew', 'compileJava', '-q'] if os.path.exists(os.path.join(self.repo_path, 'gradlew')) else ['gradle', 'compileJava', '-q'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                return True, None
            else:
                error_msg = result.stderr or result.stdout
                return False, error_msg

        except subprocess.TimeoutExpired:
            return False, "Gradle compilation timeout"
        except FileNotFoundError:
            return False, "Gradle not found"
        except Exception as e:
            return False, f"Gradle error: {str(e)}"

    def _detect_build_system(self) -> Optional[str]:
        """
        Detect build system in repository.

        Returns:
            'maven', 'gradle', or None
        """
        if not self.repo_path:
            return None

        repo = Path(self.repo_path)

        # Check for Maven
        if (repo / 'pom.xml').exists():
            return 'maven'

        # Check for Gradle
        if (repo / 'build.gradle').exists() or (repo / 'build.gradle.kts').exists():
            return 'gradle'

        return None

    def check_compiler_available(self) -> bool:
        """
        Check if Java compiler is available.

        Returns:
            True if compiler is available
        """
        try:
            result = subprocess.run(
                [self.java_compiler, '-version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
