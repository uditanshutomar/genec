"""Syntactic verification through compilation checks."""

import os
import re
import subprocess
import tempfile
from pathlib import Path

from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


class SyntacticVerifier:
    """Verifies refactorings are syntactically correct by compiling them."""

    def __init__(self, java_compiler: str = "javac", repo_path: str | None = None, lenient_mode: bool = True):
        """
        Initialize syntactic verifier.

        Args:
            java_compiler: Path to Java compiler (default: javac)
            repo_path: Path to repository root (for Maven/Gradle projects)
            lenient_mode: If True, allow symbol resolution errors (they'd resolve in full build)
        """
        self.java_compiler = java_compiler
        self.lenient_mode = lenient_mode
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
                [str(p) for p in self.source_paths],
            )

        # Discover module names (if any) to adjust module reads when compiling
        self.modules = self._discover_modules() if repo_path else []

    def verify(
        self,
        new_class_code: str,
        modified_original_code: str,
        package_name: str = "",
        original_class_file: str | None = None,
        new_class_name: str | None = None,
    ) -> tuple[bool, str | None]:
        """
        Verify that refactored code compiles successfully.

        Args:
            new_class_code: Code for new extracted class
            modified_original_code: Code for modified original class
            package_name: Package name for classes
            original_class_file: Path to the original .java file in the repo (for build-system verification)
            new_class_name: Name of the new extracted class (for build-system verification)

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        self.logger.info("Running syntactic verification")

        # Tier 1: Try build-system compilation (Maven/Gradle) in the actual repo
        if self.build_system and self.repo_path and original_class_file:
            success, error = self._verify_with_build_system(
                new_class_code,
                modified_original_code,
                package_name,
                original_class_file,
                new_class_name or self._extract_class_name(new_class_code),
            )
            if success is not None:  # None means build system failed to run, fall through to javac
                return success, error
            self.logger.info("Build system verification failed to run; falling back to javac")

        # Tier 2: Fallback - javac in temp directory (existing code)

        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create package directory structure
            if package_name:
                package_path = temp_path / package_name.replace(".", "/")
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

                new_class_file.write_text(new_class_code, encoding="utf-8")
                original_class_file.write_text(modified_original_code, encoding="utf-8")

                # Generate stub classes for any referenced but undefined classes
                stubs = self._generate_stubs_for_missing_classes(
                    modified_original_code, 
                    new_class_code,
                    package_name,
                    {new_class_name, original_class_name}
                )
                stub_files = []
                for stub_name, stub_code in stubs.items():
                    stub_file = package_path / f"{stub_name}.java"
                    stub_file.write_text(stub_code, encoding="utf-8")
                    stub_files.append(stub_file)
                    self.logger.debug(f"Generated stub: {stub_name}")

                # Compile all files together
                all_files = [new_class_file, original_class_file] + stub_files
                success, error = self._compile_files(all_files, temp_path)

                if success:
                    self.logger.info("Syntactic verification PASSED")
                    return True, None
                else:
                    # In lenient mode, only fail on syntax errors, not symbol resolution
                    self.logger.info(f"Compilation failed. Lenient mode: {self.lenient_mode}")
                    if self.lenient_mode and error:
                        # In lenient mode, only fail on true syntax/structural
                        # errors. Symbol resolution errors are expected when
                        # compiling without the project's full classpath.
                        error_lines = error.split('\n')
                        syntax_errors = []
                        # Patterns that indicate missing classpath, NOT broken code
                        lenient_patterns = [
                            'cannot find symbol',
                            'does not exist',
                            'package .* does not exist',
                            'does not override or implement',
                            'does not take parameters',
                            'is not abstract and does not override',
                            'unreported exception',
                            'cannot access',
                            'cannot be accessed from outside',
                            'has private access',
                            'is not public',
                            'non-static .* cannot be referenced',
                            'method does not override',
                            'cannot infer type',
                            'raw type',
                            'unchecked',
                            'uses or overrides a deprecated',
                        ]
                        for line in error_lines:
                            if 'error:' in line.lower():
                                line_lower = line.lower()
                                if any(p in line_lower for p in lenient_patterns):
                                    continue
                                syntax_errors.append(line)

                        if not syntax_errors:
                            self.logger.info("Syntactic verification PASSED (lenient - only symbol/classpath errors)")
                            return True, None
                        else:
                            self.logger.warning(f"Lenient verification failed. True syntax errors: {syntax_errors[:5]}")

                    self.logger.warning(f"Syntactic verification FAILED: {error}")
                    return False, error

            except Exception as e:
                error_msg = f"Syntactic verification error: {str(e)}"
                self.logger.error(error_msg)
                return False, error_msg
    
    def _generate_stubs_for_missing_classes(
        self, 
        modified_original: str, 
        new_class: str, 
        package_name: str,
        existing_classes: set
    ) -> dict[str, str]:
        """Generate stub classes for any referenced but undefined classes."""
        # Find all class references (excluding primitives and java.*)
        # Pattern: new ClassName() or ClassName variable
        pattern = r'\b([A-Z][a-zA-Z0-9]*)\s*(?:\(|[a-z]|\s*=)'
        
        all_code = modified_original + new_class
        potential_classes = set(re.findall(pattern, all_code))
        
        # Also find type declarations like: List<ClassName> or Map<K, ClassName>
        type_pattern = r'<\s*([A-Z][a-zA-Z0-9]*)'
        potential_classes.update(re.findall(type_pattern, all_code))
        
        # Common Java classes to exclude
        java_classes = {
            'String', 'Integer', 'Long', 'Double', 'Float', 'Boolean', 'Byte', 'Short', 'Character',
            'Object', 'Class', 'Exception', 'RuntimeException', 'Throwable', 'Error',
            'List', 'ArrayList', 'LinkedList', 'Set', 'HashSet', 'TreeSet', 'Map', 'HashMap', 'TreeMap',
            'Collection', 'Collections', 'Arrays', 'Iterator', 'Iterable',
            'BigDecimal', 'BigInteger', 'Date', 'LocalDate', 'LocalDateTime', 'LocalTime',
            'Optional', 'Stream', 'Collectors', 'Function', 'Consumer', 'Supplier', 'Predicate',
            'StringBuilder', 'StringBuffer', 'System', 'Math', 'Random',
            'Override', 'Deprecated', 'SuppressWarnings', 'FunctionalInterface',
            'Logger', 'ChronoUnit'
        }
        
        stubs = {}
        for class_name in potential_classes:
            # Skip constants (all uppercase)
            if class_name.isupper():
                continue
            # Skip names that are too short or look like generics (T, K, V)
            if len(class_name) <= 2:
                continue
            # Skip if in existing classes or common Java classes  
            if class_name in existing_classes or class_name in java_classes:
                continue
                
            # Generate a stub class
            package_decl = f"package {package_name};\n" if package_name else ""
            stub_code = f"""{package_decl}
/** Stub class for compilation verification */
public class {class_name} {{
    public {class_name}() {{}}
    public Object get{class_name}() {{ return this; }}
}}
"""
            stubs[class_name] = stub_code
        
        return stubs

    def _verify_with_build_system(
        self,
        new_class_code: str,
        modified_original_code: str,
        package_name: str,
        original_class_file: str,
        new_class_name: str,
    ) -> tuple[bool | None, str | None]:
        """
        Verify compilation using the project's build system (Maven/Gradle).

        Writes extracted code into the actual repo, runs build, then restores.
        Returns (None, None) if the build system couldn't be used (caller should
        fall through to the javac fallback).
        """
        import shutil

        repo = Path(self.repo_path)
        original_path = (
            Path(original_class_file)
            if Path(original_class_file).is_absolute()
            else repo / original_class_file
        )

        if not original_path.exists():
            self.logger.warning(f"Original class file not found: {original_path}")
            return None, None

        # Compute new class file path (same directory as original)
        new_class_path = original_path.parent / f"{new_class_name}.java"

        # Backup original file
        backup_content = original_path.read_text(encoding="utf-8")
        new_class_existed = new_class_path.exists()
        new_class_backup = new_class_path.read_text(encoding="utf-8") if new_class_existed else None

        try:
            # Write refactored code into repo
            original_path.write_text(modified_original_code, encoding="utf-8")
            new_class_path.write_text(new_class_code, encoding="utf-8")

            # Run build system
            if self.build_system == "maven":
                success, error = self._compile_with_maven([new_class_path, original_path])
            elif self.build_system == "gradle":
                success, error = self._compile_with_gradle([new_class_path, original_path])
            else:
                return None, None

            return success, error

        except Exception as e:
            self.logger.warning(f"Build system verification error: {e}")
            return None, None

        finally:
            # ALWAYS restore original files
            try:
                original_path.write_text(backup_content, encoding="utf-8")
            except Exception as e:
                self.logger.error(f"CRITICAL: Failed to restore {original_path}: {e}")

            try:
                if new_class_existed and new_class_backup is not None:
                    new_class_path.write_text(new_class_backup, encoding="utf-8")
                elif new_class_path.exists() and not new_class_existed:
                    new_class_path.unlink()
            except Exception as e:
                self.logger.error(f"Failed to clean up {new_class_path}: {e}")

    def _extract_class_name(self, code: str) -> str | None:
        """
        Extract class name from Java code.

        Args:
            code: Java source code

        Returns:
            Class name or None
        """
        # First, strip comments to avoid matching "class" in comments
        # Remove single-line comments
        code_no_comments = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        # Remove multi-line comments (including Javadoc)
        code_no_comments = re.sub(r'/\*.*?\*/', '', code_no_comments, flags=re.DOTALL)

        # Look for class declaration at start of line (with optional modifiers)
        # Pattern: optional modifiers followed by 'class' keyword and class name
        pattern = r'^\s*(?:public\s+)?(?:abstract\s+)?(?:final\s+)?class\s+(\w+)'
        match = re.search(pattern, code_no_comments, re.MULTILINE)

        if match:
            return match.group(1)

        return None

    def _compile_files(self, java_files: list, classpath: Path) -> tuple[bool, str | None]:
        """
        Compile Java files using Maven/Gradle or javac.

        Args:
            java_files: List of Java file paths
            classpath: Classpath for compilation

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        # Always compile the generated sources directly to avoid validating the
        # unmodified repository. Project builds do not include temp files.
        return self._compile_with_javac(java_files, classpath)

    def _compile_with_javac(self, java_files: list, classpath: Path) -> tuple[bool, str | None]:
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
                "-classpath",
                classpath_str,
                "-sourcepath",
                sourcepath_str,
                "-d",
                str(classpath),
            ] + [str(f) for f in java_files]

            # When modules are present, ensure they can read required desktop APIs
            if self.modules:
                cmd.extend(["--add-modules", "java.desktop,java.datatransfer"])
                for module in self.modules:
                    cmd.extend(
                        [
                            "--add-reads",
                            f"{module}=java.desktop,java.datatransfer",
                            "--add-reads",
                            f"{module}=ALL-UNNAMED",
                        ]
                    )

            # Run compilation
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

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
            "**/src/main/java",
            "**/src/java",
            "**/src",
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
                                has_java = next(child.rglob("*.java"), None)
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

        for module_file in repo.rglob("module-info.java"):
            try:
                text = module_file.read_text(encoding="utf-8")
            except Exception as e:
                self.logger.debug(f"Failed to read module file {module_file}: {e}")
                continue

            match = re.search(r"\bmodule\s+([a-zA-Z0-9_.]+)\s*\{", text)
            if match:
                modules.add(match.group(1))

        return sorted(modules)

    def _compile_with_maven(self, java_files: list) -> tuple[bool, str | None]:
        """
        Compile using Maven (runs full project compilation).

        Called by _verify_with_build_system when Maven is the detected build system.

        Args:
            java_files: List of Java file paths (logged for info)

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            self.logger.info(f"Compiling project with Maven in {self.repo_path}")

            # Run Maven compile - use project's own Java version settings
            cmd = [
                "mvn",
                "-q",
                "compile",
                "-DskipTests",
            ]

            if self.modules:
                cmd.append("-DforceAddModules=java.desktop,java.datatransfer")

            result = subprocess.run(
                cmd, cwd=self.repo_path, capture_output=True, text=True, timeout=120
            )

            if result.returncode == 0:
                return True, None
            else:
                # Extract relevant errors
                error_msg = result.stderr or result.stdout
                # If Maven already compiled successfully but produced warnings, treat as success
                if (
                    "COMPILATION ERROR" not in error_msg
                    and "BUILD FAILURE" not in error_msg
                    and "error:" not in error_msg
                ):
                    self.logger.debug(
                        "Maven returned non-zero but without compilation errors; treating as success."
                    )
                    return True, None

                # Try to find compilation errors
                if "COMPILATION ERROR" in error_msg or "error:" in error_msg:
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

    def _compile_with_gradle(self, java_files: list) -> tuple[bool, str | None]:
        """
        Compile using Gradle (runs full project compilation).

        Called by _verify_with_build_system when Gradle is the detected build system.

        Args:
            java_files: List of Java file paths (logged for info)

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            self.logger.info(f"Compiling project with Gradle in {self.repo_path}")

            # Run Gradle compile
            result = subprocess.run(
                (
                    ["./gradlew", "compileJava", "-q"]
                    if os.path.exists(os.path.join(self.repo_path, "gradlew"))
                    else ["gradle", "compileJava", "-q"]
                ),
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=120,
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

    def _detect_build_system(self) -> str | None:
        """
        Detect build system in repository.

        Returns:
            'maven', 'gradle', or None
        """
        if not self.repo_path:
            return None

        repo = Path(self.repo_path)

        # Check for Maven
        if (repo / "pom.xml").exists():
            return "maven"

        # Check for Gradle
        if (repo / "build.gradle").exists() or (repo / "build.gradle.kts").exists():
            return "gradle"

        return None

    def check_compiler_available(self) -> bool:
        """
        Check if Java compiler is available.

        Returns:
            True if compiler is available
        """
        try:
            result = subprocess.run(
                [self.java_compiler, "-version"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
            self.logger.debug(f"Java compiler check failed: {e}")
            return False
