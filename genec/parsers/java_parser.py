"""Java source code parser using javalang."""

import javalang
from typing import List, Dict, Optional, Set
from pathlib import Path
from dataclasses import dataclass

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

    def extract_class_info(self, tree: javalang.tree.CompilationUnit,
                          source_code: str) -> Optional[Dict]:
        """
        Extract class information from AST.

        Args:
            tree: Parsed AST
            source_code: Original source code

        Returns:
            Dictionary with class information
        """
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
