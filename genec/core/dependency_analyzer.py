"""Static dependency analyzer for Java classes."""

from dataclasses import dataclass, field

import numpy as np

from genec.parsers.java_parser import JavaParser
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class MethodInfo:
    """Information about a method in a class."""

    name: str
    signature: str
    return_type: str
    modifiers: list[str]
    parameters: list[dict]
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
    modifiers: list[str]
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
    methods: list[MethodInfo] = field(default_factory=list)
    fields: list[FieldInfo] = field(default_factory=list)
    constructors: list[MethodInfo] = field(default_factory=list)
    method_calls: dict[str, list[str]] = field(default_factory=dict)  # method -> called methods
    field_accesses: dict[str, list[str]] = field(default_factory=dict)  # method -> accessed fields
    dependency_matrix: np.ndarray | None = None
    member_names: list[str] = field(default_factory=list)  # All members (methods + fields)

    def get_all_methods(self) -> list[MethodInfo]:
        """Get all methods including constructors."""
        return self.methods + self.constructors


# ── Shared dependency weights (used by all analyzers) ─────────────────────────
WEIGHT_METHOD_CALL = 1.0
WEIGHT_FIELD_ACCESS = 0.8
WEIGHT_SHARED_FIELD = 0.9


def build_dependency_matrix(
    class_deps: "ClassDependencies",
    weight_method_call: float = WEIGHT_METHOD_CALL,
    weight_field_access: float = WEIGHT_FIELD_ACCESS,
    weight_shared_field: float = WEIGHT_SHARED_FIELD,
) -> None:
    """Build dependency matrix for all members (methods + fields).

    Populates ``class_deps.member_names`` and ``class_deps.dependency_matrix``.
    Extracted as a module-level function so that both DependencyAnalyzer and
    HybridDependencyAnalyzer share the exact same logic and weights.

    Args:
        class_deps: ClassDependencies object to populate.
        weight_method_call: Weight for direct method calls.
        weight_field_access: Weight for field accesses from a method.
        weight_shared_field: Weight for implicit coupling via shared field.
    """
    all_methods = class_deps.get_all_methods()

    member_names = [m.signature for m in all_methods] + [f.name for f in class_deps.fields]
    class_deps.member_names = member_names

    n = len(member_names)
    matrix = np.zeros((n, n))

    method_to_idx = {m.signature: i for i, m in enumerate(all_methods)}
    field_to_idx = {f.name: i + len(all_methods) for i, f in enumerate(class_deps.fields)}

    name_to_methods: dict[str, list[MethodInfo]] = {}
    for method in all_methods:
        name_to_methods.setdefault(method.name, []).append(method)

    for method in all_methods:
        method_idx = method_to_idx[method.signature]

        # Method calls
        for called_method in class_deps.method_calls.get(method.signature, []):
            if "(" in called_method and called_method in method_to_idx:
                called_idx = method_to_idx[called_method]
                matrix[method_idx][called_idx] = weight_method_call
                continue

            called_name = called_method.split("(", 1)[0] if "(" in called_method else called_method
            overloaded_methods = name_to_methods.get(called_name, [])
            if len(overloaded_methods) == 1:
                called_idx = method_to_idx[overloaded_methods[0].signature]
                matrix[method_idx][called_idx] = weight_method_call
            elif len(overloaded_methods) > 1:
                weight = weight_method_call * 0.9
                for overloaded_method in overloaded_methods:
                    called_idx = method_to_idx[overloaded_method.signature]
                    matrix[method_idx][called_idx] = max(matrix[method_idx][called_idx], weight)

        # Field accesses
        for field_name in class_deps.field_accesses.get(method.signature, []):
            if field_name in field_to_idx:
                field_idx = field_to_idx[field_name]
                matrix[method_idx][field_idx] = weight_field_access

    # Add shared field dependencies (methods accessing same field)
    for field_name, field_idx in field_to_idx.items():
        accessing_methods = []
        for method in all_methods:
            if field_name in class_deps.field_accesses.get(method.signature, []):
                accessing_methods.append(method_to_idx[method.signature])

        for i in range(len(accessing_methods)):
            for j in range(i + 1, len(accessing_methods)):
                idx1, idx2 = accessing_methods[i], accessing_methods[j]
                matrix[idx1][idx2] = max(matrix[idx1][idx2], weight_shared_field)
                matrix[idx2][idx1] = max(matrix[idx2][idx1], weight_shared_field)

    class_deps.dependency_matrix = matrix


class DependencyAnalyzer:
    """Analyzes static dependencies in Java classes."""

    # Dependency weights (module-level constants are authoritative)
    WEIGHT_METHOD_CALL = WEIGHT_METHOD_CALL
    WEIGHT_FIELD_ACCESS = WEIGHT_FIELD_ACCESS
    WEIGHT_SHARED_FIELD = WEIGHT_SHARED_FIELD

    def __init__(self):
        """Initialize the dependency analyzer."""
        self.parser = JavaParser()
        self.logger = get_logger(self.__class__.__name__)

    def analyze_class(self, class_file: str) -> ClassDependencies | None:
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
            with open(class_file, encoding="utf-8") as f:
                source_code = f.read()
        except Exception as e:
            self.logger.error(f"Failed to read {class_file}: {e}")
            return None

        # Extract class information (parser will handle priority and lazy parsing)
        class_info = self.parser.extract_class_info(None, source_code, class_file)
        if not class_info:
            self.logger.error(f"Failed to extract class info from {class_file}")
            return None

        # Convert to our data structures
        methods = []
        for parsed_method in class_info["methods"]:
            method_info = MethodInfo(
                name=parsed_method.name,
                signature=parsed_method.signature,
                return_type=parsed_method.return_type,
                modifiers=parsed_method.modifiers,
                parameters=parsed_method.parameters,
                start_line=parsed_method.start_line,
                end_line=parsed_method.end_line,
                body=parsed_method.body,
            )
            methods.append(method_info)

        constructors = []
        for parsed_constructor in class_info["constructors"]:
            constructor_info = MethodInfo(
                name=parsed_constructor.name,
                signature=parsed_constructor.signature,
                return_type="",
                modifiers=parsed_constructor.modifiers,
                parameters=parsed_constructor.parameters,
                start_line=parsed_constructor.start_line,
                end_line=parsed_constructor.end_line,
                body=parsed_constructor.body,
            )
            constructors.append(constructor_info)

        fields = []
        for parsed_field in class_info["fields"]:
            field_info = FieldInfo(
                name=parsed_field.name,
                type=parsed_field.type,
                modifiers=parsed_field.modifiers,
                line_number=parsed_field.line_number,
            )
            fields.append(field_info)

        # Create ClassDependencies object
        class_deps = ClassDependencies(
            class_name=class_info["class_name"],
            package_name=class_info["package_name"],
            file_path=class_file,
            methods=methods,
            fields=fields,
            constructors=constructors,
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
        method_names = {m.name for m in all_methods}
        name_arity_to_methods: dict[tuple[str, int], list[MethodInfo]] = {}
        for method_info in all_methods:
            name_arity_to_methods.setdefault(
                (method_info.name, len(method_info.parameters)), []
            ).append(method_info)

        for method in all_methods:
            # Extract method calls
            body = method.body or ""
            called_methods = self.parser.extract_method_calls_with_arity(body)
            # Filter to only methods in this class
            internal_calls: list[str] = []
            seen = set()
            for called_name, argc in called_methods:
                if called_name not in method_names:
                    continue

                # Try to resolve overloads by arity when available
                target = None
                if argc is not None:
                    candidates = name_arity_to_methods.get((called_name, argc), [])
                    if len(candidates) == 1:
                        target = candidates[0].signature

                if target is None:
                    target = called_name

                if target not in seen:
                    internal_calls.append(target)
                    seen.add(target)

            class_deps.method_calls[method.signature] = internal_calls

            # Extract field accesses
            accessed_fields = self.parser.extract_field_accesses(body)
            # Filter to only fields in this class
            internal_accesses = [f for f in accessed_fields if f in field_names]
            class_deps.field_accesses[method.signature] = internal_accesses

    def _build_dependency_matrix(self, class_deps: ClassDependencies):
        """Build dependency matrix — delegates to shared module-level function."""
        build_dependency_matrix(class_deps)

    def get_dependency_strength(
        self, class_deps: ClassDependencies, member1: str, member2: str
    ) -> float:
        """
        Get dependency strength between two members.

        Args:
            class_deps: ClassDependencies object
            member1: First member name
            member2: Second member name

        Returns:
            Dependency strength (0.0 if no dependency or matrix is None)
        """
        # Check if dependency matrix exists
        if class_deps.dependency_matrix is None:
            return 0.0

        if member1 not in class_deps.member_names or member2 not in class_deps.member_names:
            return 0.0

        idx1 = class_deps.member_names.index(member1)
        idx2 = class_deps.member_names.index(member2)

        return class_deps.dependency_matrix[idx1][idx2]
