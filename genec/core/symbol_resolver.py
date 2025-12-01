"""Symbol resolution for Java classes."""

from dataclasses import dataclass


@dataclass
class ImportInfo:
    """Information about an import statement."""

    path: str
    static: bool
    wildcard: bool


class SymbolResolver:
    """Resolves simple names to fully qualified names using imports."""

    def __init__(self, imports: list[dict]):
        """
        Initialize symbol resolver.

        Args:
            imports: List of import dictionaries from JavaParser
        """
        self.imports = [
            ImportInfo(
                path=i["path"], static=i.get("static", False), wildcard=i.get("wildcard", False)
            )
            for i in imports
        ]

        # Cache for resolved names
        self._type_cache: dict[str, str] = {}
        self._static_cache: dict[str, str] = {}

    def resolve_type(self, simple_name: str) -> str:
        """
        Resolve a simple type name to its fully qualified name.

        Args:
            simple_name: Simple type name (e.g., "List", "List<String>")

        Returns:
            Fully qualified name (e.g., "java.util.List") or original if not found
        """
        # Handle generics: List<String> -> List
        base_name = simple_name.split("<")[0].strip()

        # Check cache
        if base_name in self._type_cache:
            return self._type_cache[base_name]

        # 1. Check direct imports
        for imp in self.imports:
            if not imp.wildcard and not imp.static:
                # import java.util.List;
                if imp.path.endswith(f".{base_name}"):
                    resolved = imp.path
                    self._type_cache[base_name] = resolved
                    return resolved

        # 2. Check wildcard imports (heuristic: assume it might be in one of them)
        # Note: Without scanning the classpath, we can't be 100% sure which wildcard contains it.
        # For now, we return the simple name if not directly imported,
        # unless we want to guess (e.g. java.lang is implicit).

        # Implicit java.lang check (common types)
        java_lang_types = {
            "String",
            "Integer",
            "Boolean",
            "Double",
            "Long",
            "Object",
            "System",
            "Math",
            "Exception",
            "Thread",
        }
        if base_name in java_lang_types:
            return f"java.lang.{base_name}"

        return base_name

    def resolve_static_member(self, member_name: str) -> str | None:
        """
        Resolve a statically imported member.

        Args:
            member_name: Name of the static member (e.g., "max")

        Returns:
            Fully qualified name (e.g., "java.lang.Math.max") or None if not found
        """
        if member_name in self._static_cache:
            return self._static_cache[member_name]

        for imp in self.imports:
            if imp.static:
                if imp.wildcard:
                    # import static java.lang.Math.*;
                    # We can't be sure without checking the class, but we can return the class path
                    # as a potential source.
                    pass
                elif imp.path.endswith(f".{member_name}"):
                    # import static java.lang.Math.max;
                    self._static_cache[member_name] = imp.path
                    return imp.path

        return None
