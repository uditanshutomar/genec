"""
Eclipse JDT-based code generation for Extract Class refactorings.

This module provides a code generator that delegates to Eclipse JDT
for production-quality, guaranteed-correct Java refactoring.

Architecture:
    GenEC (Python) → JDT Wrapper (Java/JDT) → Refactored Code

    GenEC handles:
    - Dependency analysis
    - Clustering
    - AI-powered naming

    Eclipse JDT handles:
    - Code generation
    - Type checking
    - Refactoring execution
"""

import json
import subprocess
import os
from pathlib import Path
from typing import Optional

from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import ClassDependencies
from genec.core.code_generator import GeneratedCode, CodeGenerationError
from genec.utils.logging_utils import get_logger


logger = get_logger(__name__)


class JDTCodeGenerator:
    """
    Code generator using Eclipse JDT for Extract Class refactoring.

    This is a production-ready alternative to string-based code generation.
    Uses Eclipse JDT's battle-tested refactoring engine (15+ years of development).
    """

    def __init__(
        self,
        jdt_wrapper_jar: Optional[str] = None,
        timeout: int = 60
    ):
        """
        Initialize JDT code generator.

        Args:
            jdt_wrapper_jar: Path to genec-jdt-wrapper JAR file.
                           If None, looks in default location.
            timeout: Timeout for JDT process in seconds
        """
        self.logger = get_logger(self.__class__.__name__)
        self.timeout = timeout

        # Find JDT wrapper JAR
        if jdt_wrapper_jar is None:
            jdt_wrapper_jar = self._find_jdt_wrapper()

        if not os.path.exists(jdt_wrapper_jar):
            raise FileNotFoundError(
                f"Eclipse JDT wrapper JAR not found: {jdt_wrapper_jar}\n"
                f"Please build it with: cd genec-jdt-wrapper && mvn package"
            )

        self.jdt_wrapper_jar = jdt_wrapper_jar
        self.logger.info(f"Using Eclipse JDT wrapper: {jdt_wrapper_jar}")

    def _find_jdt_wrapper(self) -> str:
        """Find JDT wrapper JAR in default locations."""
        possible_locations = [
            "genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar",
            "lib/genec-jdt-wrapper.jar",
            "../genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar"
        ]

        for location in possible_locations:
            if os.path.exists(location):
                return location

        # Default to expected Maven output location
        return possible_locations[0]

    def generate(
        self,
        cluster: Cluster,
        new_class_name: str,
        class_file: str,
        repo_path: str,
        class_deps: ClassDependencies
    ) -> GeneratedCode:
        """
        Generate refactored code using Eclipse JDT.

        GenEC provides:
        - cluster: What methods/fields to extract
        - new_class_name: Name from LLM
        - class_file: Source file

        Eclipse JDT provides:
        - Actual refactoring execution
        - Type-safe code generation
        - Guaranteed correctness

        Args:
            cluster: Cluster to extract
            new_class_name: Name for new class (from LLM)
            class_file: Path to Java source file
            repo_path: Path to repository root
            class_deps: Class dependencies (for field inference)

        Returns:
            GeneratedCode with new_class_code and modified_original_code

        Raises:
            CodeGenerationError: If JDT refactoring fails
        """
        self.logger.info(
            f"Generating refactoring for cluster {cluster.id} "
            f"using Eclipse JDT: {new_class_name}"
        )

        # Infer fields if not explicitly in cluster
        fields = list(cluster.get_fields())
        if not fields:
            fields = self._infer_fields(cluster, class_deps)
            self.logger.info(f"Inferred fields: {fields}")

        # Build refactoring specification
        spec = {
            'projectPath': repo_path,
            'classFile': class_file,
            'newClassName': new_class_name,
            'methods': cluster.get_methods(),
            'fields': fields
        }

        self.logger.debug(f"Refactoring spec: {json.dumps(spec, indent=2)}")

        # Call Eclipse JDT wrapper
        result = self._call_jdt_wrapper(spec)

        # Parse result
        if not result.get('success', False):
            raise CodeGenerationError(
                f"Eclipse JDT refactoring failed: {result.get('message', 'Unknown error')}"
            )

        self.logger.info(f"Eclipse JDT refactoring successful: {result.get('message')}")

        return GeneratedCode(
            new_class_code=result.get('newClassCode', ''),
            modified_original_code=result.get('modifiedOriginalCode', '')
        )

    def _call_jdt_wrapper(self, spec: dict) -> dict:
        """
        Call Eclipse JDT wrapper via subprocess.

        Args:
            spec: Refactoring specification

        Returns:
            Result dictionary from JDT wrapper

        Raises:
            CodeGenerationError: If subprocess call fails
        """
        spec_json = json.dumps(spec)

        try:
            # Execute JDT wrapper
            result = subprocess.run(
                ['java', '-jar', self.jdt_wrapper_jar, '--spec', spec_json],
                capture_output=True,
                text=True,
                timeout=self.timeout
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
                    raise CodeGenerationError(
                        f"Eclipse JDT process failed with exit code {result.returncode}\n"
                        f"stdout: {result.stdout}\n"
                        f"stderr: {result.stderr}"
                    )

        except subprocess.TimeoutExpired:
            raise CodeGenerationError(
                f"Eclipse JDT process timed out after {self.timeout} seconds"
            )
        except FileNotFoundError:
            raise CodeGenerationError(
                "Java runtime not found. Please ensure Java 11+ is installed."
            )
        except Exception as e:
            raise CodeGenerationError(f"Error calling Eclipse JDT wrapper: {str(e)}")

    def _infer_fields(self, cluster: Cluster, class_deps: ClassDependencies) -> list:
        """
        Infer fields accessed by cluster methods.

        Uses ClassDependencies.field_accesses to determine which fields
        are used by methods in the cluster.

        Args:
            cluster: Cluster to analyze
            class_deps: Class dependencies with field access information

        Returns:
            List of field names accessed by cluster methods
        """
        used_fields = set()

        for method_sig in cluster.get_methods():
            # Get fields accessed by this method
            accessed = class_deps.field_accesses.get(method_sig, [])
            used_fields.update(accessed)

        return list(used_fields)

    def is_available(self) -> bool:
        """
        Check if Eclipse JDT wrapper is available.

        Returns:
            True if JDT wrapper JAR exists and Java is available
        """
        if not os.path.exists(self.jdt_wrapper_jar):
            return False

        try:
            # Check if Java is available
            result = subprocess.run(
                ['java', '-version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
