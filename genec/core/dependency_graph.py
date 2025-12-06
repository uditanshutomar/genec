"""
Dependency graph for multi-file refactoring.

Builds a workspace-level dependency graph to:
1. Detect inter-file dependencies
2. Suggest optimal refactoring order
3. Identify circular dependencies that would block extraction
"""

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from genec.utils.logging_utils import get_logger


@dataclass
class ClassNode:
    """Represents a class in the dependency graph."""
    name: str
    file_path: Path
    package: str
    dependencies: set[str] = field(default_factory=set)  # Classes this class imports
    dependents: set[str] = field(default_factory=set)  # Classes that import this class
    
    @property
    def fully_qualified_name(self) -> str:
        return f"{self.package}.{self.name}" if self.package else self.name


@dataclass
class DependencyGraph:
    """Graph of class dependencies for multi-file analysis."""
    nodes: dict[str, ClassNode] = field(default_factory=dict)
    
    def add_class(self, node: ClassNode):
        """Add a class to the graph."""
        self.nodes[node.name] = node
    
    def get_dependency_order(self, class_names: list[str]) -> list[str]:
        """
        Get optimal order for refactoring classes (dependencies first).
        
        Uses topological sort to ensure dependencies are refactored before dependents.
        
        Args:
            class_names: List of class names to order
            
        Returns:
            Ordered list (dependencies first, dependents last)
        """
        # Filter to only requested classes
        subset = {name for name in class_names if name in self.nodes}
        
        # Build in-degree map for topological sort
        in_degree = {name: 0 for name in subset}
        for name in subset:
            node = self.nodes[name]
            for dep in node.dependencies:
                if dep in subset:
                    in_degree[name] += 1
        
        # Kahn's algorithm for topological sort
        result = []
        queue = [name for name, degree in in_degree.items() if degree == 0]
        
        while queue:
            current = queue.pop(0)
            result.append(current)
            
            # Reduce in-degree of dependents
            for name in subset:
                node = self.nodes[name]
                if current in node.dependencies:
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        queue.append(name)
        
        # Check for cycles
        if len(result) != len(subset):
            # Cycle detected - return in original order with warning
            return list(class_names)
        
        return result
    
    def detect_cycles(self, class_names: list[str]) -> list[tuple[str, str]]:
        """
        Detect circular dependencies among specified classes.
        
        Args:
            class_names: List of class names to check
            
        Returns:
            List of (class_a, class_b) pairs that form cycles
        """
        cycles = []
        subset = {name for name in class_names if name in self.nodes}
        
        for name in subset:
            node = self.nodes[name]
            for dep in node.dependencies:
                if dep in subset:
                    dep_node = self.nodes.get(dep)
                    if dep_node and name in dep_node.dependencies:
                        # Mutual dependency = cycle
                        pair = tuple(sorted([name, dep]))
                        if pair not in cycles:
                            cycles.append(pair)
        
        return cycles


class DependencyAnalyzer:
    """Analyzes dependencies across multiple files."""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
    
    def build_graph(self, files: list[Path]) -> DependencyGraph:
        """
        Build dependency graph for given Java files.
        
        Args:
            files: List of Java file paths to analyze
            
        Returns:
            DependencyGraph with all class relationships
        """
        import re
        
        graph = DependencyGraph()
        
        for file_path in files:
            try:
                content = file_path.read_text(encoding='utf-8')
                
                # Extract package
                package_match = re.search(r'package\s+([\w.]+)\s*;', content)
                package = package_match.group(1) if package_match else ""
                
                # Extract class name
                class_match = re.search(
                    r'(?:public\s+)?(?:abstract\s+)?(?:final\s+)?(?:class|interface|enum)\s+(\w+)',
                    content
                )
                if not class_match:
                    continue
                class_name = class_match.group(1)
                
                # Extract imports (dependencies)
                imports = re.findall(r'import\s+([\w.]+)\.(\w+)\s*;', content)
                dependencies = {imp[1] for imp in imports}  # Just class names
                
                # Also find direct type references
                type_refs = re.findall(r'\b([A-Z][a-zA-Z0-9_]*)\b', content)
                # Filter to likely class names (not keywords, not this class)
                JAVA_KEYWORDS = {'String', 'Integer', 'Boolean', 'Double', 'Float', 
                               'Long', 'Short', 'Byte', 'Character', 'Object',
                               'List', 'Map', 'Set', 'Collection', 'Optional',
                               'Exception', 'Error', 'Override', 'Deprecated'}
                type_refs = {ref for ref in type_refs 
                            if ref not in JAVA_KEYWORDS and ref != class_name}
                
                # Add node
                node = ClassNode(
                    name=class_name,
                    file_path=file_path,
                    package=package,
                    dependencies=dependencies,
                )
                graph.add_class(node)
                
            except Exception as e:
                self.logger.debug(f"Failed to analyze {file_path}: {e}")
        
        # Build reverse dependencies (dependents)
        for name, node in graph.nodes.items():
            for dep in node.dependencies:
                if dep in graph.nodes:
                    graph.nodes[dep].dependents.add(name)
        
        self.logger.info(f"Built dependency graph with {len(graph.nodes)} classes")
        return graph
    
    def suggest_refactoring_order(
        self, 
        graph: DependencyGraph, 
        target_classes: list[str]
    ) -> tuple[list[str], list[tuple[str, str]]]:
        """
        Suggest optimal refactoring order for target classes.
        
        Args:
            graph: Dependency graph
            target_classes: Classes to refactor
            
        Returns:
            Tuple of (ordered_classes, cycles) where cycles are blocking issues
        """
        cycles = graph.detect_cycles(target_classes)
        
        if cycles:
            self.logger.warning(
                f"Circular dependencies detected: {cycles}. "
                f"These classes may need manual review."
            )
        
        order = graph.get_dependency_order(target_classes)
        
        self.logger.info(f"Suggested refactoring order: {order}")
        return order, cycles
