"""Deterministic code generation for Extract Class refactorings."""

from dataclasses import dataclass
from typing import List, Tuple, Dict, Set
import re

from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import ClassDependencies, MethodInfo, FieldInfo


class CodeGenerationError(Exception):
    """Raised when deterministic code generation cannot proceed."""


@dataclass
class GeneratedCode:
    """Container for generated code artifacts."""
    new_class_code: str
    modified_original_code: str


class CodeGenerator:
    """Generates deterministic Extract Class refactoring code."""

    def __init__(self, original_code: str, class_deps: ClassDependencies):
        self.original_code = original_code
        self.class_deps = class_deps
        self.lines = original_code.splitlines()
        self.package_line = self._find_package()
        self.import_lines = self._find_imports()
        self.method_map = {m.signature: m for m in class_deps.methods}
        self.constructor_map = {c.signature: c for c in class_deps.constructors}
        self.field_map = {f.name: f for f in class_deps.fields}
        self.field_accesses = class_deps.field_accesses
        self.method_calls = class_deps.method_calls
        self.class_name = class_deps.class_name

    def generate(self, cluster: Cluster, new_class_name: str) -> GeneratedCode:
        """Generate new class and modified original code for a cluster."""
        methods = sorted(
            cluster.get_methods(),
            key=lambda sig: self.method_map[sig].start_line if sig in self.method_map else float('inf')
        )
        fields = sorted(
            cluster.get_fields(),
            key=lambda name: self.field_map[name].line_number if name in self.field_map else float('inf')
        )

        if not methods:
            raise CodeGenerationError("Cluster has no methods to extract")

        self._validate_cluster(methods, fields)

        delegate_fields = set(fields)
        inferred_fields = self._infer_delegate_fields(methods)
        delegate_fields.update(inferred_fields)

        new_class_code = self._build_new_class(methods, delegate_fields, new_class_name)
        modified_original_code = self._build_modified_original(methods, delegate_fields, new_class_name)

        return GeneratedCode(new_class_code=new_class_code, modified_original_code=modified_original_code)

    # ------------------------------------------------------------------ #
    # Validation helpers
    # ------------------------------------------------------------------ #
    def _validate_cluster(self, method_signatures: List[str], field_names: List[str]):
        """Ensure cluster can be deterministically extracted."""
        cluster_methods = set(method_signatures)
        cluster_fields = set(field_names)

        # Ensure we have MethodInfo for each signature and none are constructors/static
        for signature in cluster_methods:
            if signature not in self.method_map:
                raise CodeGenerationError(f"Method metadata missing for {signature}")
            method = self.method_map[signature]
            if 'static' in (method.modifiers or []):
                raise CodeGenerationError(f"Static methods not supported ({method.name})")
            if method.return_type == '' and method.name == self.class_deps.class_name:
                raise CodeGenerationError("Constructors cannot be extracted deterministically")

        # Methods must not call non-cluster methods within the same class
        name_to_signatures: Dict[str, List[str]] = {}
        for sig, method in self.method_map.items():
            name_to_signatures.setdefault(method.name, []).append(sig)

        for signature in cluster_methods:
            called = self.method_calls.get(signature, [])
            for called_name in called:
                candidate_sigs = name_to_signatures.get(called_name, [])
                if not any(sig in cluster_methods for sig in candidate_sigs):
                    raise CodeGenerationError(
                        f"Method '{signature}' calls '{called_name}' outside the cluster"
                    )

        # Ensure referenced fields exist
        for field in cluster_fields:
            if field not in self.field_map:
                raise CodeGenerationError(f"Field '{field}' not found in class definition")

    # ------------------------------------------------------------------ #
    # Code construction helpers
    # ------------------------------------------------------------------ #
    def _build_new_class(self, method_signatures: List[str], delegate_fields: Set[str], new_class_name: str) -> str:
        """Construct the new extracted class code."""
        builder: List[str] = []

        if self.package_line:
            builder.append(self.package_line)

        if self.import_lines:
            builder.append('')
            builder.extend(self.import_lines)

        builder.append('')
        builder.append(f"public class {new_class_name} {{")

        builder.append('')
        builder.append(f"    private final {self.class_name} owner;")

        builder.append('')
        builder.append(f"    public {new_class_name}({self.class_name} owner) {{")
        builder.append("        this.owner = owner;")
        builder.append("    }")

        for signature in sorted(method_signatures, key=lambda sig: self.method_map[sig].start_line):
            method_text = self._rewrite_method_text(signature, delegate_fields)
            builder.append('')
            for line in method_text.splitlines():
                builder.append('    ' + line)

        builder.append('}')

        return '\n'.join(builder) + '\n'

    def _build_modified_original(self, method_signatures: List[str], delegate_fields: Set[str], new_class_name: str) -> str:
        """Construct the modified original class code."""
        lines = list(self.lines)

        self._relax_field_visibility(lines, delegate_fields)

        delegate_field_name = self._delegate_field_name(new_class_name)
        for signature in sorted(method_signatures, key=lambda sig: self.method_map[sig].start_line, reverse=True):
            stub_lines, start, end = self._build_method_stub(signature, delegate_field_name)
            lines[start:end] = stub_lines

        # Insert delegate field after method replacements to avoid index shifts
        insert_idx = self._find_insertion_index(lines)
        delegate_line = f"    private final {new_class_name} {delegate_field_name} = new {new_class_name}(this);"
        lines.insert(insert_idx, delegate_line)

        modified = '\n'.join(lines)
        if not modified.endswith('\n'):
            modified += '\n'
        return modified

    def _rewrite_method_text(self, signature: str, delegate_fields: Set[str]) -> str:
        method = self.method_map[signature]
        body = method.body

        for field in delegate_fields:
            body = body.replace(f"this.{field}", f"owner.{field}")

        parameter_names = {p['name'] for p in (method.parameters or [])}

        for field in delegate_fields:
            if field in parameter_names:
                continue
            pattern = re.compile(rf"(?<!\.)\b{re.escape(field)}\b")
            body = pattern.sub(f"owner.{field}", body)

        return body

    def _infer_delegate_fields(self, method_signatures: List[str]) -> Set[str]:
        inferred: Set[str] = set()
        for signature in method_signatures:
            method = self.method_map[signature]
            body = method.body
            for field in self.field_map.keys():
                if field in inferred:
                    continue
                if re.search(rf"\b{re.escape(field)}\b", body):
                    inferred.add(field)
        return inferred

    def _relax_field_visibility(self, lines: List[str], fields: Set[str]):
        for field in fields:
            if field not in self.field_map:
                continue
            _, (start, end) = self._extract_field_text(field)
            updated_lines = []
            for idx in range(start, end):
                line = lines[idx]
                updated_line = re.sub(r'(\s*)private\s+', r'\1', line, count=1)
                updated_lines.append(updated_line)
            lines[start:end] = updated_lines

    # ------------------------------------------------------------------ #
    # Extraction helpers
    # ------------------------------------------------------------------ #
    def _extract_field_text(self, field_name: str) -> Tuple[List[str], Tuple[int, int]]:
        """Return field declaration lines and their range."""
        field_info: FieldInfo = self.field_map[field_name]
        start = field_info.line_number - 1
        if start < 0 or start >= len(self.lines):
            raise CodeGenerationError(f"Invalid line number for field {field_name}")

        lines: List[str] = []
        idx = start
        while idx < len(self.lines):
            line = self.lines[idx]
            lines.append(line)
            if ';' in line:
                idx += 1
                break
            idx += 1

        return lines, (start, idx)

    def _extract_method_text(self, signature: str) -> List[str]:
        """Return method text lines for inclusion in new class."""
        method: MethodInfo = self.method_map[signature]
        method_lines = method.body.splitlines()
        return method_lines

    def _build_method_stub(self, signature: str, delegate_field: str) -> Tuple[List[str], int, int]:
        """Create delegation stub for the original class."""
        method = self.method_map[signature]
        start = method.start_line - 1
        end = method.end_line

        body = method.body
        brace_index = body.find('{')
        if brace_index == -1:
            raise CodeGenerationError(f"Method body parsing failed for {signature}")

        header_text = body[:brace_index].rstrip()
        header_lines = header_text.splitlines()
        last_header_line = header_lines[-1] if header_lines else ''
        indent_match = re.match(r'\s*', last_header_line)
        indent = indent_match.group(0) if indent_match else ''

        params = method.parameters or []
        param_names = ', '.join(p['name'] for p in params)

        call = f"{delegate_field}.{method.name}({param_names})" if param_names else f"{delegate_field}.{method.name}()"
        if method.return_type == 'void':
            call_line = f"{indent}    {call};"
        else:
            call_line = f"{indent}    return {call};"

        stub_lines = list(header_lines)
        stub_lines.append(f"{indent}" + '{')
        stub_lines.append(call_line)
        stub_lines.append(f"{indent}" + '}')

        return stub_lines, start, end

    # ------------------------------------------------------------------ #
    # Utility helpers
    # ------------------------------------------------------------------ #
    def _find_package(self) -> str:
        for line in self.lines:
            stripped = line.strip()
            if stripped.startswith('package '):
                return stripped
        return ''

    def _find_imports(self) -> List[str]:
        imports = []
        for line in self.lines:
            stripped = line.strip()
            if stripped.startswith('import '):
                imports.append(stripped)
        return imports

    def _delegate_field_name(self, class_name: str) -> str:
        if not class_name:
            return 'extracted'
        return class_name[0].lower() + class_name[1:]

    def _find_insertion_index(self, lines: List[str]) -> int:
        class_name = self.class_deps.class_name
        for idx, line in enumerate(lines):
            if f"class {class_name}" in line:
                # Find first line with '{' (may be same line)
                if '{' in line:
                    return idx + 1
                probe = idx + 1
                while probe < len(lines):
                    if '{' in lines[probe]:
                        return probe + 1
                    probe += 1
        return len(lines)
