"""Static dependency analyzer for Java classes."""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from pathlib import Path

from genec.parsers.java_parser import JavaParser, ParsedMethod, ParsedField
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class MethodInfo:
    """Information about a method in a class."""
    name: str
    signature: str
    return_type: str
    modifiers: List[str]
    parameters: List[dict]
    start_line: int
    end_line: int
    body: str

    def __hash__(self):
        return hash(self.signature)

    def __eq__(self, other):
        if isinstance(other, MethodInfo):
            return self.signature == other.signature
        return False


@dataclass
class FieldInfo:
    """Information about a field in a class."""
    name: str
    type: str
    modifiers: List[str]
    line_number: int

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, FieldInfo):
            return self.name == other.name
        return False


@dataclass
class ClassDependencies:
    """Complete dependency information for a Java class."""
    class_name: str
    package_name: str
    file_path: str
    methods: List[MethodInfo] = field(default_factory=list)
    fields: List[FieldInfo] = field(default_factory=list)
    constructors: List[MethodInfo] = field(default_factory=list)
    method_calls: Dict[str, List[str]] = field(default_factory=dict)  # method -> called methods
    field_accesses: Dict[str, List[str]] = field(default_factory=dict)  # method -> accessed fields
    dependency_matrix: Optional[np.ndarray] = None
    member_names: List[str] = field(default_factory=list)  # All members (methods + fields)

    def get_all_methods(self) -> List[MethodInfo]:
        """Get all methods including constructors."""
        return self.methods + self.constructors


class DependencyAnalyzer:
    """Analyzes static dependencies in Java classes."""

    # Dependency weights
    WEIGHT_METHOD_CALL = 1.0
    WEIGHT_FIELD_ACCESS = 0.8
    WEIGHT_SHARED_FIELD = 0.6

    def __init__(self):
        """Initialize the dependency analyzer."""
        self.parser = JavaParser()
        self.logger = get_logger(self.__class__.__name__)

    def analyze_class(self, class_file: str) -> Optional[ClassDependencies]:
        """
        Analyze a Java class file and extract all dependencies.

        Args:
            class_file: Path to Java class file

        Returns:
            ClassDependencies object or None if analysis fails
        """
        self.logger.info(f"Analyzing class: {class_file}")

        # Read source code
        try:
            with open(class_file, 'r', encoding='utf-8') as f:
                source_code = f.read()
        except Exception as e:
            self.logger.error(f"Failed to read {class_file}: {e}")
            return None

        # Parse AST
        tree = self.parser.parse_file(class_file)
        if not tree:
            self.logger.error(f"Failed to parse AST for {class_file}")
            return None

        # Extract class information
        class_info = self.parser.extract_class_info(tree, source_code)
        if not class_info:
            self.logger.error(f"Failed to extract class info from {class_file}")
            return None

        # Convert to our data structures
        methods = []
        for parsed_method in class_info['methods']:
            method_info = MethodInfo(
                name=parsed_method.name,
                signature=parsed_method.signature,
                return_type=parsed_method.return_type,
                modifiers=parsed_method.modifiers,
                parameters=parsed_method.parameters,
                start_line=parsed_method.start_line,
                end_line=parsed_method.end_line,
                body=parsed_method.body
            )
            methods.append(method_info)

        constructors = []
        for parsed_constructor in class_info['constructors']:
            constructor_info = MethodInfo(
                name=parsed_constructor.name,
                signature=parsed_constructor.signature,
                return_type='',
                modifiers=parsed_constructor.modifiers,
                parameters=parsed_constructor.parameters,
                start_line=parsed_constructor.start_line,
                end_line=parsed_constructor.end_line,
                body=parsed_constructor.body
            )
            constructors.append(constructor_info)

        fields = []
        for parsed_field in class_info['fields']:
            field_info = FieldInfo(
                name=parsed_field.name,
                type=parsed_field.type,
                modifiers=parsed_field.modifiers,
                line_number=parsed_field.line_number
            )
            fields.append(field_info)

        # Create ClassDependencies object
        class_deps = ClassDependencies(
            class_name=class_info['class_name'],
            package_name=class_info['package_name'],
            file_path=class_file,
            methods=methods,
            fields=fields,
            constructors=constructors
        )

        # Extract method calls and field accesses
        self._extract_dependencies(class_deps)

        # Build dependency matrix
        self._build_dependency_matrix(class_deps)

        self.logger.info(
            f"Analyzed {class_deps.class_name}: "
            f"{len(methods)} methods, {len(constructors)} constructors, "
            f"{len(fields)} fields"
        )

        return class_deps

    def _extract_dependencies(self, class_deps: ClassDependencies):
        """
        Extract method calls and field accesses for all methods.

        Args:
            class_deps: ClassDependencies object to populate
        """
        all_methods = class_deps.get_all_methods()
        field_names = {f.name for f in class_deps.fields}

        for method in all_methods:
            # Extract method calls
            called_methods = self.parser.extract_method_calls(method.body)
            # Filter to only methods in this class
            method_names = {m.name for m in all_methods}
            internal_calls = [m for m in called_methods if m in method_names]
            class_deps.method_calls[method.signature] = internal_calls

            # Extract field accesses
            accessed_fields = self.parser.extract_field_accesses(method.body)
            # Filter to only fields in this class
            internal_accesses = [f for f in accessed_fields if f in field_names]
            class_deps.field_accesses[method.signature] = internal_accesses

    def _build_dependency_matrix(self, class_deps: ClassDependencies):
        """
        Build dependency matrix for all members (methods + fields).

        Matrix[i][j] represents dependency strength from member i to member j.

        Args:
            class_deps: ClassDependencies object to populate
        """
        all_methods = class_deps.get_all_methods()

        # Create member name list (methods first, then fields)
        member_names = [m.signature for m in all_methods] + [f.name for f in class_deps.fields]
        class_deps.member_names = member_names

        n = len(member_names)
        matrix = np.zeros((n, n))

        # Create index maps
        method_to_idx = {m.signature: i for i, m in enumerate(all_methods)}
        field_to_idx = {f.name: i + len(all_methods) for i, f in enumerate(class_deps.fields)}

        # Fill matrix with dependencies
        for method in all_methods:
            method_idx = method_to_idx[method.signature]

            # Method calls
            for called_method_name in class_deps.method_calls.get(method.signature, []):
                # Find the called method's signature
                for m in all_methods:
                    if m.name == called_method_name:
                        called_idx = method_to_idx[m.signature]
                        matrix[method_idx][called_idx] = self.WEIGHT_METHOD_CALL

            # Field accesses
            for field_name in class_deps.field_accesses.get(method.signature, []):
                if field_name in field_to_idx:
                    field_idx = field_to_idx[field_name]
                    matrix[method_idx][field_idx] = self.WEIGHT_FIELD_ACCESS

        # Add shared field dependencies (methods accessing same field)
        for field_name, field_idx in field_to_idx.items():
            accessing_methods = []
            for method in all_methods:
                if field_name in class_deps.field_accesses.get(method.signature, []):
                    accessing_methods.append(method_to_idx[method.signature])

            # Create connections between methods that access the same field
            for i in range(len(accessing_methods)):
                for j in range(i + 1, len(accessing_methods)):
                    idx1, idx2 = accessing_methods[i], accessing_methods[j]
                    # Add bidirectional shared field dependency
                    matrix[idx1][idx2] = max(matrix[idx1][idx2], self.WEIGHT_SHARED_FIELD)
                    matrix[idx2][idx1] = max(matrix[idx2][idx1], self.WEIGHT_SHARED_FIELD)

        class_deps.dependency_matrix = matrix

    def get_dependency_strength(self, class_deps: ClassDependencies,
                               member1: str, member2: str) -> float:
        """
        Get dependency strength between two members.

        Args:
            class_deps: ClassDependencies object
            member1: First member name
            member2: Second member name

        Returns:
            Dependency strength (0.0 if no dependency)
        """
        if member1 not in class_deps.member_names or member2 not in class_deps.member_names:
            return 0.0

        idx1 = class_deps.member_names.index(member1)
        idx2 = class_deps.member_names.index(member2)

        return class_deps.dependency_matrix[idx1][idx2]
