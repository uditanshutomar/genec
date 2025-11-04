"""Java source code parser using javalang with JDT fallback."""

import os
import javalang
from typing import List, Dict, Optional, Set, Tuple
from pathlib import Path
from dataclasses import dataclass

try:
    from tree_sitter_languages import get_parser as ts_get_parser
except ImportError:  # pragma: no cover - handled gracefully in runtime
    ts_get_parser = None

from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ParsedMethod:
    """Represents a parsed Java method."""
    name: str
    signature: str
    return_type: str
    modifiers: List[str]
    parameters: List[Dict[str, str]]
    start_line: int
    end_line: int
    body: str
    is_constructor: bool = False

    def full_signature(self) -> str:
        """Get full method signature including return type."""
        params = ", ".join([f"{p['type']} {p['name']}" for p in self.parameters])
        if self.is_constructor:
            return f"{self.name}({params})"
        return f"{self.return_type} {self.name}({params})"


@dataclass
class ParsedField:
    """Represents a parsed Java field."""
    name: str
    type: str
    modifiers: List[str]
    line_number: int


class JavaParser:
    """Parser for Java source code using javalang."""

    def __init__(self):
        """Initialize the Java parser."""
        self.logger = get_logger(self.__class__.__name__)
        self.ts_parser = None
        if ts_get_parser:
            try:
                self.ts_parser = ts_get_parser("java")
            except Exception as exc:  # pragma: no cover
                self.logger.warning(f"Failed to initialize tree-sitter parser: {exc}")
        self.inspector_jar_path = self._find_jdt_wrapper()

    def parse_file(self, file_path: str) -> Optional[javalang.tree.CompilationUnit]:
        """
        Parse a Java file and return the AST.

        Args:
            file_path: Path to Java source file

        Returns:
            Parsed compilation unit or None if parsing fails
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            return javalang.parse.parse(source_code)
        except Exception as e:
            self.logger.error(f"Failed to parse {file_path}: {e}")
            return None

    def parse_file_content(self, source_code: str) -> Optional[javalang.tree.CompilationUnit]:
        """
        Parse Java source provided as a string.

        Args:
            source_code: Raw Java source code

        Returns:
            Parsed compilation unit or None if parsing fails
        """
        try:
            return javalang.parse.parse(source_code)
        except Exception as e:
            self.logger.error(f"Failed to parse source content: {e}")
            return None

    def _extract_class_info_javalang(self, tree: javalang.tree.CompilationUnit,
                                     source_code: str) -> Optional[Dict]:
        """Extract class information using javalang AST."""
        if not tree:
            return None

        source_lines = source_code.split('\n')

        # Find the main class declaration
        for path, node in tree.filter(javalang.tree.ClassDeclaration):
            package_name = tree.package.name if tree.package else ""

            class_info = {
                'class_name': node.name,
                'package_name': package_name,
                'modifiers': node.modifiers or [],
                'extends': node.extends.name if node.extends else None,
                'implements': [impl.name for impl in (node.implements or [])],
                'methods': [],
                'fields': [],
                'constructors': []
            }

            # Extract fields
            for field_decl in node.fields:
                for declarator in field_decl.declarators:
                    field_info = ParsedField(
                        name=declarator.name,
                        type=self._get_type_name(field_decl.type),
                        modifiers=field_decl.modifiers or [],
                        line_number=field_decl.position.line if field_decl.position else 0
                    )
                    class_info['fields'].append(field_info)

            # Extract methods and constructors
            for method in node.methods:
                start_line = method.position.line if method.position else 0
                end_line = self._find_method_end_line(source_lines, start_line)

                method_body = '\n'.join(source_lines[start_line-1:end_line])

                parameters = []
                if method.parameters:
                    for param in method.parameters:
                        parameters.append({
                            'name': param.name,
                            'type': self._get_type_name(param.type)
                        })

                parsed_method = ParsedMethod(
                    name=method.name,
                    signature=self._build_signature(method.name, parameters),
                    return_type=self._get_type_name(method.return_type) if method.return_type else 'void',
                    modifiers=method.modifiers or [],
                    parameters=parameters,
                    start_line=start_line,
                    end_line=end_line,
                    body=method_body,
                    is_constructor=False
                )

                class_info['methods'].append(parsed_method)

            # Extract constructors
            for constructor in node.constructors:
                start_line = constructor.position.line if constructor.position else 0
                end_line = self._find_method_end_line(source_lines, start_line)

                method_body = '\n'.join(source_lines[start_line-1:end_line])

                parameters = []
                if constructor.parameters:
                    for param in constructor.parameters:
                        parameters.append({
                            'name': param.name,
                            'type': self._get_type_name(param.type)
                        })

                parsed_constructor = ParsedMethod(
                    name=constructor.name,
                    signature=self._build_signature(constructor.name, parameters),
                    return_type='',
                    modifiers=constructor.modifiers or [],
                    parameters=parameters,
                    start_line=start_line,
                    end_line=end_line,
                    body=method_body,
                    is_constructor=True
                )

                class_info['constructors'].append(parsed_constructor)

            return class_info

        return None

    def extract_class_info(self, tree: Optional[javalang.tree.CompilationUnit],
                           source_code: str,
                           file_path: Optional[str] = None) -> Optional[Dict]:
        """
        Extract class information. Falls back to tree-sitter when javalang fails.

        Args:
            tree: Parsed AST (may be None if javalang parsing failed)
            source_code: Original source code

        Returns:
            Dictionary with class information or None if parsing fails
        """
        info = self._extract_class_info_javalang(tree, source_code)
        if info:
            return info

        info = self._fallback_to_tree_sitter(source_code)
        if info:
            return info

        if file_path:
            info = self._fallback_to_jdt_inspector(file_path)
            if info:
                return info

        return None

    def _fallback_to_tree_sitter(self, source_code: str) -> Optional[Dict]:
        if not self.ts_parser:
            return None
        try:
            return self._extract_class_info_tree_sitter(source_code)
        except Exception as exc:
            self.logger.error(f"Tree-sitter extraction failed: {exc}")
            return None

    def _fallback_to_jdt_inspector(self, file_path: str) -> Optional[Dict]:
        jar_path = self._get_inspector_jar()
        if not jar_path:
            return None

        import json
        import subprocess

        try:
            result = subprocess.run(
                ['java', '-cp', jar_path, 'com.genec.jdt.ClassInspector', '--file', file_path],
                capture_output=True,
                text=True,
                check=True
            )
        except Exception as exc:
            self.logger.error(f"JDT ClassInspector failed: {exc}")
            return None

        try:
            payload = json.loads(result.stdout)
        except Exception as exc:
            self.logger.error(f"Failed to parse ClassInspector output: {exc}")
            return None

        return self._convert_inspector_payload(payload)

    def _extract_class_info_tree_sitter(self, source_code: str) -> Optional[Dict]:
        """Extract class information using tree-sitter."""
        if not self.ts_parser:
            return None

        source_bytes = source_code.encode('utf-8')
        tree = self.ts_parser.parse(source_bytes)
        root = tree.root_node

        class_node = self._find_first(root, "class_declaration")
        if class_node is None:
            return None

        package_name = ""
        package_node = self._find_first(root, "package_declaration")
        if package_node is not None:
            package_text = self._node_text(package_node, source_bytes)
            package_text = package_text.replace("package", "", 1).strip()
            if package_text.endswith(";"):
                package_text = package_text[:-1].strip()
            package_name = package_text

        name_node = class_node.child_by_field_name("name")
        class_name = self._node_text(name_node, source_bytes) if name_node else ""

        extends_node = class_node.child_by_field_name("superclass")
        extends_name = self._node_text(extends_node, source_bytes) if extends_node else None

        implements_node = class_node.child_by_field_name("interfaces")
        implements_list: List[str] = []
        if implements_node:
            for child in self._collect_descendants(implements_node, "type_identifier"):
                text = self._node_text(child, source_bytes)
                if text:
                    implements_list.append(text)

        class_info = {
            'class_name': class_name,
            'package_name': package_name,
            'modifiers': self._collect_modifiers(class_node, source_bytes),
            'extends': extends_name,
            'implements': implements_list,
            'methods': [],
            'fields': [],
            'constructors': []
        }

        field_nodes = self._collect_descendants(class_node, "field_declaration")
        for field_node in field_nodes:
            type_node = field_node.child_by_field_name("type")
            field_type = self._node_text(type_node, source_bytes) if type_node else ""
            modifiers = self._collect_modifiers(field_node, source_bytes)

            for declarator in self._collect_descendants(field_node, "variable_declarator"):
                name_node = declarator.child_by_field_name("name")
                field_name = self._node_text(name_node, source_bytes)
                if not field_name:
                    continue
                line_number = declarator.start_point[0] + 1
                parsed_field = ParsedField(
                    name=field_name.strip(),
                    type=field_type.strip(),
                    modifiers=modifiers,
                    line_number=line_number
                )
                class_info['fields'].append(parsed_field)

        method_nodes = self._collect_descendants(class_node, "method_declaration")
        for method_node in method_nodes:
            parsed_method = self._build_parsed_method_from_ts(
                method_node,
                source_code,
                source_bytes,
                is_constructor=False
            )
            if parsed_method:
                class_info['methods'].append(parsed_method)

        constructor_nodes = self._collect_descendants(class_node, "constructor_declaration")
        for ctor_node in constructor_nodes:
            parsed_ctor = self._build_parsed_method_from_ts(
                ctor_node,
                source_code,
                source_bytes,
                is_constructor=True
            )
            if parsed_ctor:
                class_info['constructors'].append(parsed_ctor)

        return class_info

    def _build_parsed_method_from_ts(
        self,
        node,
        source_code: str,
        source_bytes: bytes,
        is_constructor: bool
    ) -> Optional[ParsedMethod]:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return None
        method_name = self._node_text(name_node, source_bytes).strip()

        parameters = self._collect_parameters_from_ts(node, source_bytes)
        signature = self._build_signature(method_name, parameters)

        return_type = ''
        if not is_constructor:
            return_node = node.child_by_field_name("type")
            if return_node is None:
                # Some grammars use 'return_type' field
                return_node = node.child_by_field_name("return_type")
            return_type = self._node_text(return_node, source_bytes).strip() if return_node else 'void'

        modifiers = self._collect_modifiers(node, source_bytes)

        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        body_text = source_code[node.start_byte:node.end_byte]

        return ParsedMethod(
            name=method_name,
            signature=signature,
            return_type=return_type,
            modifiers=modifiers,
            parameters=parameters,
            start_line=start_line,
            end_line=end_line,
            body=body_text,
            is_constructor=is_constructor
        )

    def _collect_parameters_from_ts(self, node, source_bytes: bytes) -> List[Dict[str, str]]:
        parameters: List[Dict[str, str]] = []
        params_node = node.child_by_field_name("parameters")
        if not params_node:
            params_node = node.child_by_field_name("formal_parameters")
        if not params_node:
            return parameters

        for param in self._collect_descendants(params_node, "formal_parameter"):
            type_node = param.child_by_field_name("type")
            name_node = param.child_by_field_name("name")
            if not name_node:
                continue
            param_type = self._node_text(type_node, source_bytes).strip() if type_node else ""
            param_name = self._node_text(name_node, source_bytes).strip()
            parameters.append({
                'name': param_name,
                'type': param_type
            })
        return parameters

    def _collect_modifiers(self, node, source_bytes: bytes) -> List[str]:
        modifiers: List[str] = []
        for child in node.children:
            if child.type == 'modifiers':
                for mod in child.children:
                    text = self._node_text(mod, source_bytes).strip()
                    if text:
                        modifiers.append(text)
            elif child.type in {'modifier', 'annotation', 'marker_annotation'}:
                text = self._node_text(child, source_bytes).strip()
                if text:
                    modifiers.append(text)
        return modifiers

    def _collect_descendants(self, node, target_type: str) -> List:
        result = []
        stack = [node]
        while stack:
            current = stack.pop()
            if current.type == target_type:
                result.append(current)
            stack.extend(reversed(current.children))
        return result

    def _find_first(self, node, target_type: str):
        stack = [node]
        while stack:
            current = stack.pop()
            if current.type == target_type:
                return current
            stack.extend(reversed(current.children))
        return None

    def _node_text(self, node, source_bytes: bytes) -> str:
        if node is None:
            return ""
        return source_bytes[node.start_byte:node.end_byte].decode('utf-8')

    def _find_jdt_wrapper(self) -> Optional[str]:
        candidates = [
            "genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar",
            "genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0.jar",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _get_inspector_jar(self) -> Optional[str]:
        if self.inspector_jar_path and os.path.exists(self.inspector_jar_path):
            return self.inspector_jar_path
        jar_path = self._find_jdt_wrapper()
        self.inspector_jar_path = jar_path
        return jar_path

    def _convert_inspector_payload(self, payload: Dict) -> Optional[Dict]:
        try:
            class_info = {
                'class_name': payload.get('className', ''),
                'package_name': payload.get('packageName', ''),
                'modifiers': payload.get('modifiers', []),
                'extends': payload.get('extends', None),
                'implements': payload.get('implements', []),
                'methods': [],
                'fields': [],
                'constructors': []
            }

            for field_data in payload.get('fields', []):
                class_info['fields'].append(
                    ParsedField(
                        name=field_data.get('name', ''),
                        type=field_data.get('type', ''),
                        modifiers=field_data.get('modifiers', []),
                        line_number=field_data.get('line', 0)
                    )
                )

            for method_data in payload.get('methods', []):
                class_info['methods'].append(
                    ParsedMethod(
                        name=method_data.get('name', ''),
                        signature=method_data.get('signature', ''),
                        return_type=method_data.get('returnType', 'void'),
                        modifiers=method_data.get('modifiers', []),
                        parameters=method_data.get('parameters', []),
                        start_line=method_data.get('startLine', 0),
                        end_line=method_data.get('endLine', 0),
                        body=method_data.get('body', ''),
                        is_constructor=False
                    )
                )

            for ctor_data in payload.get('constructors', []):
                class_info['constructors'].append(
                    ParsedMethod(
                        name=ctor_data.get('name', ''),
                        signature=ctor_data.get('signature', ''),
                        return_type='',
                        modifiers=ctor_data.get('modifiers', []),
                        parameters=ctor_data.get('parameters', []),
                        start_line=ctor_data.get('startLine', 0),
                        end_line=ctor_data.get('endLine', 0),
                        body=ctor_data.get('body', ''),
                        is_constructor=True
                    )
                )

            return class_info
        except Exception as exc:
            self.logger.error(f"Failed to convert inspector payload: {exc}")
            return None

    def extract_method_calls(self, method_body: str) -> Set[str]:
        """
        Extract method calls from method body.

        Args:
            method_body: Source code of method body

        Returns:
            Set of called method names
        """
        called_methods = set()

        try:
            # Try to parse as a method body
            # Wrap in a dummy class and method for parsing
            wrapped = f"class Dummy {{ void dummy() {{ {method_body} }} }}"
            tree = javalang.parse.parse(wrapped)

            for path, node in tree.filter(javalang.tree.MethodInvocation):
                called_methods.add(node.member)

        except Exception as e:
            self.logger.debug(f"Failed to extract method calls: {e}")

        return called_methods

    def extract_field_accesses(self, method_body: str) -> Set[str]:
        """
        Extract field accesses from method body.

        Args:
            method_body: Source code of method body

        Returns:
            Set of accessed field names
        """
        accessed_fields = set()

        try:
            # Try to parse as a method body
            wrapped = f"class Dummy {{ void dummy() {{ {method_body} }} }}"
            tree = javalang.parse.parse(wrapped)

            for path, node in tree.filter(javalang.tree.MemberReference):
                accessed_fields.add(node.member)

        except Exception as e:
            self.logger.debug(f"Failed to extract field accesses: {e}")

        return accessed_fields

    def _get_type_name(self, type_ref) -> str:
        """Extract type name from type reference."""
        if type_ref is None:
            return "void"
        if isinstance(type_ref, str):
            return type_ref
        if hasattr(type_ref, 'name'):
            return type_ref.name
        if hasattr(type_ref, 'type'):
            return self._get_type_name(type_ref.type)
        return str(type_ref)

    def _build_signature(self, method_name: str, parameters: List[Dict[str, str]]) -> str:
        """Build method signature string."""
        param_types = [p['type'] for p in parameters]
        return f"{method_name}({','.join(param_types)})"

    def _find_method_end_line(self, source_lines: List[str], start_line: int) -> int:
        """
        Find the end line of a method by counting braces.

        Args:
            source_lines: Source code lines
            start_line: Method start line (1-indexed)

        Returns:
            End line number (1-indexed)
        """
        brace_count = 0
        in_method = False

        for i in range(start_line - 1, len(source_lines)):
            line = source_lines[i]

            for char in line:
                if char == '{':
                    brace_count += 1
                    in_method = True
                elif char == '}':
                    brace_count -= 1
                    if in_method and brace_count == 0:
                        return i + 1

        return len(source_lines)
