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
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import ClassDependencies
from genec.utils.logging_utils import get_logger


class CodeGenerationError(Exception):
    """Raised when deterministic code generation cannot proceed."""


@dataclass
class GeneratedCode:
    """Container for generated code artifacts."""

    new_class_code: str
    modified_original_code: str


logger = get_logger(__name__)


class JDTCodeGenerator:
    """
    Code generator using Eclipse JDT for Extract Class refactoring.

    This is a production-ready alternative to string-based code generation.
    Uses Eclipse JDT's battle-tested refactoring engine (15+ years of development).
    """

    def __init__(self, jdt_wrapper_jar: str | None = None, timeout: int = 60):
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
        project_root = Path(__file__).parent.parent.parent

        possible_locations = [
            # Relative paths (legacy)
            "genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar",
            "lib/genec-jdt-wrapper.jar",
            # Absolute paths relative to project root
            str(
                project_root
                / "genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar"
            ),
            str(project_root / "lib/genec-jdt-wrapper.jar"),
        ]

        for location in possible_locations:
            if os.path.exists(location):
                return location

        # Default to expected Maven output location (absolute)
        return str(
            project_root
            / "genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar"
        )

    def generate(
        self,
        cluster: Cluster,
        new_class_name: str,
        class_file: str,
        repo_path: str,
        class_deps: ClassDependencies,
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

        original_method_set = set(cluster.get_methods())
        methods = self._augment_methods(cluster, class_deps)
        if set(methods) != original_method_set:
            self.logger.info(
                "Added helper methods to extraction cluster: %s",
                sorted(set(methods) - original_method_set),
            )

        # Infer fields if not explicitly in cluster
        fields = list(cluster.get_fields())
        if not fields:
            fields = self._infer_fields(cluster, class_deps)
            self.logger.info(f"Inferred fields: {fields}")

        if not methods:
            raise CodeGenerationError(
                "JDT extraction requires at least one method. "
                f"Cluster {cluster.id} has {len(fields)} fields but 0 methods. "
                "Field-only extraction is not currently supported."
            )

        # Validate inputs
        if not new_class_name or not new_class_name.isidentifier():
            raise CodeGenerationError(f"Invalid new class name: '{new_class_name}'")

        # Filter and validate methods
        valid_methods = [m for m in methods if m and isinstance(m, str) and m.strip()]
        if len(valid_methods) != len(methods):
            self.logger.warning(
                f"Filtered out {len(methods) - len(valid_methods)} invalid/empty method signatures"
            )
        methods = valid_methods

        if not methods:
            raise CodeGenerationError(
                "JDT extraction requires at least one valid method signature. "
                f"Cluster {cluster.id} has {len(fields)} fields but 0 valid methods."
            )

        # Build refactoring specification
        spec = {
            "projectPath": repo_path,
            "classFile": class_file,
            "newClassName": new_class_name,
            "methods": methods,
            "fields": fields,
        }

        self.logger.debug(f"Refactoring spec: {json.dumps(spec, indent=2)}")

        # Call Eclipse JDT wrapper
        result = self._call_jdt_wrapper(spec)

        # Parse result
        if not result.get("success", False):
            raise CodeGenerationError(
                f"Eclipse JDT refactoring failed: {result.get('message', 'Unknown error')}"
            )

        self.logger.info(f"Eclipse JDT refactoring successful: {result.get('message')}")

        return GeneratedCode(
            new_class_code=result.get("newClassCode", ""),
            modified_original_code=result.get("modifiedOriginalCode", ""),
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
                ["java", "-jar", self.jdt_wrapper_jar, "--spec", spec_json],
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
                    raise CodeGenerationError(
                        f"Eclipse JDT process failed with exit code {result.returncode}\n"
                        f"stdout: {result.stdout}\n"
                        f"stderr: {result.stderr}"
                    )

        except subprocess.TimeoutExpired:
            raise CodeGenerationError(f"Eclipse JDT process timed out after {self.timeout} seconds")
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
        cluster_methods = set(cluster.get_methods())

        # 1. Identify all fields accessed by cluster methods
        for method_sig in cluster_methods:
            accessed = class_deps.field_accesses.get(method_sig, [])
            used_fields.update(accessed)
            
        if not used_fields:
            return []

        # 2. Identify fields used by non-cluster methods (external usage)
        external_usage = set()
        for method_sig, accessed_fields in class_deps.field_accesses.items():
            if method_sig not in cluster_methods:
                external_usage.update(accessed_fields)

        # 3. Filter to keep only exclusively used fields
        exclusive_fields = [f for f in used_fields if f not in external_usage]
        
        # Log excluded fields for debugging
        excluded = used_fields - set(exclusive_fields)
        if excluded:
            self.logger.debug(f"Excluded shared fields: {excluded}")

        return exclusive_fields

    def _augment_methods(self, cluster: Cluster, class_deps: ClassDependencies) -> list[str]:
        """
        Ensure the extraction includes private helper methods required by the cluster.
        """
        methods: set[str] = set(cluster.get_methods())
        if not methods:
            return []

        # Map method names to signatures and modifiers for quick lookup
        name_to_sigs: dict[str, list[str]] = {}
        modifiers_by_sig: dict[str, list[str]] = {}
        method_by_sig: dict[str, ClassDependencies] = {}
        for method in class_deps.methods:
            name_to_sigs.setdefault(method.name, []).append(method.signature)
            modifiers_by_sig[method.signature] = method.modifiers or []
            method_by_sig[method.signature] = method

        candidate_names = set(name_to_sigs.keys())
        initial_method_names = {sig.split("(")[0] for sig in methods}

        # 1. Add ALL overloads of initially selected methods
        # This ensures API consistency (e.g., if remove(int) is selected, remove(long) is too)
        for name in initial_method_names:
            for sig in name_to_sigs.get(name, []):
                if sig not in methods:
                    methods.add(sig)
                    self.logger.debug(f"Added overload: {sig}")

        added = True
        while added:
            added = False
            for signature in list(methods):
                called_names = set(class_deps.method_calls.get(signature, []))
                method_info = method_by_sig.get(signature)
                if method_info and method_info.body:
                    called_names.update(
                        self._find_called_method_names(method_info.body, candidate_names)
                    )

                for called_name in called_names:
                    for candidate_sig in name_to_sigs.get(called_name, []):
                        if candidate_sig in methods:
                            continue
                        modifiers = [m.lower() for m in modifiers_by_sig.get(candidate_sig, [])]
                        
                        should_add = False
                        
                        # Add private helper methods
                        if "private" in modifiers:
                            should_add = True
                            
                        # Add package-private helper methods (no visibility modifier)
                        # Treat them like private helpers as they are often implementation details
                        elif not any(m in modifiers for m in ["public", "protected"]):
                            should_add = True
                            
                        # Add static helper methods (they're often utilities used by the cluster)
                        elif "static" in modifiers:
                            should_add = True
                            
                        if should_add:
                            methods.add(candidate_sig)
                            added = True
                            self.logger.debug(f"Added dependency: {candidate_sig}")

        # Update cluster metadata so downstream components know about new methods
        for sig in methods:
            if sig not in cluster.member_types or cluster.member_types[sig] != "method":
                cluster.member_types[sig] = "method"
                if sig not in cluster.member_names:
                    cluster.member_names.append(sig)

        return list(methods)

    def _find_called_method_names(self, body: str, candidates: set[str]) -> set[str]:
        names: set[str] = set()
        for match in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", body):
            name = match.group(1)
            if name in candidates and name not in self._KEYWORD_BLACKLIST:
                names.add(name)
        return names

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
            result = subprocess.run(["java", "-version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False

    _KEYWORD_BLACKLIST = {
        "if",
        "for",
        "while",
        "switch",
        "return",
        "new",
        "super",
        "this",
        "catch",
        "throw",
        "else",
        "case",
        "do",
        "try",
        "default",
        "assert",
        "synchronized",
    }
