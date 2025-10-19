"""Coupling metrics calculator (CBO)."""

import javalang
from typing import Set, List, Dict

from genec.core.dependency_analyzer import ClassDependencies
from genec.parsers.java_parser import JavaParser
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


class CouplingCalculator:
    """Calculates coupling metrics for Java classes."""

    def __init__(self):
        """Initialize coupling calculator."""
        self.parser = JavaParser()
        self.logger = get_logger(self.__class__.__name__)

    def calculate_cbo(
        self,
        class_deps: ClassDependencies,
        project_classes: List[str] = None
    ) -> int:
        """
        Calculate CBO (Coupling Between Objects).

        CBO counts the number of classes that this class is coupled to.

        A class is coupled to another if it:
        - Has a field of that class type
        - Has a method parameter of that class type
        - Has a method return type of that class type
        - Calls a method or accesses a field of that class

        Args:
            class_deps: ClassDependencies object
            project_classes: List of class names in the project (optional)

        Returns:
            CBO count (number of coupled classes)
        """
        coupled_classes = set()

        # Extract types from fields
        for field in class_deps.fields:
            field_type = self._extract_base_type(field.type)
            if field_type and self._is_project_class(field_type, project_classes):
                coupled_classes.add(field_type)

        # Extract types from methods
        for method in class_deps.get_all_methods():
            # Return type
            return_type = self._extract_base_type(method.return_type)
            if return_type and self._is_project_class(return_type, project_classes):
                coupled_classes.add(return_type)

            # Parameter types
            for param in method.parameters:
                param_type = self._extract_base_type(param['type'])
                if param_type and self._is_project_class(param_type, project_classes):
                    coupled_classes.add(param_type)

        # Remove self-reference
        if class_deps.class_name in coupled_classes:
            coupled_classes.remove(class_deps.class_name)

        cbo = len(coupled_classes)

        self.logger.debug(f"CBO = {cbo} (coupled to: {coupled_classes})")

        return cbo

    def calculate_afferent_coupling(
        self,
        class_name: str,
        all_class_deps: List[ClassDependencies]
    ) -> int:
        """
        Calculate afferent coupling (Ca).

        Ca = number of classes that depend on this class.

        Args:
            class_name: Name of the class
            all_class_deps: List of all class dependencies in the project

        Returns:
            Afferent coupling count
        """
        ca = 0

        for other_class_deps in all_class_deps:
            if other_class_deps.class_name == class_name:
                continue

            # Check if other class depends on this class
            if self._class_depends_on(other_class_deps, class_name):
                ca += 1

        self.logger.debug(f"Afferent coupling for {class_name} = {ca}")

        return ca

    def calculate_efferent_coupling(
        self,
        class_deps: ClassDependencies,
        all_class_names: List[str]
    ) -> int:
        """
        Calculate efferent coupling (Ce).

        Ce = number of classes that this class depends on.
        This is essentially the same as CBO.

        Args:
            class_deps: ClassDependencies object
            all_class_names: List of all class names in the project

        Returns:
            Efferent coupling count
        """
        return self.calculate_cbo(class_deps, all_class_names)

    def calculate_instability(
        self,
        class_name: str,
        class_deps: ClassDependencies,
        all_class_deps: List[ClassDependencies]
    ) -> float:
        """
        Calculate instability metric (I).

        I = Ce / (Ca + Ce)

        Where:
        - Ce = efferent coupling (outgoing)
        - Ca = afferent coupling (incoming)

        Range: [0, 1]
        - 0 = maximally stable (only incoming dependencies)
        - 1 = maximally unstable (only outgoing dependencies)

        Args:
            class_name: Name of the class
            class_deps: ClassDependencies object
            all_class_deps: List of all class dependencies

        Returns:
            Instability value (0.0 to 1.0)
        """
        all_class_names = [cd.class_name for cd in all_class_deps]

        ce = self.calculate_efferent_coupling(class_deps, all_class_names)
        ca = self.calculate_afferent_coupling(class_name, all_class_deps)

        if ce + ca == 0:
            return 0.0

        instability = ce / (ca + ce)

        self.logger.debug(f"Instability for {class_name} = {instability:.4f} (Ce={ce}, Ca={ca})")

        return instability

    def _extract_base_type(self, type_string: str) -> str:
        """
        Extract base type from a type string.

        Handles generics, arrays, etc.

        Args:
            type_string: Type string (e.g., "List<String>", "int[]")

        Returns:
            Base type name
        """
        if not type_string:
            return ""

        # Remove generics
        if '<' in type_string:
            type_string = type_string[:type_string.index('<')]

        # Remove array brackets
        type_string = type_string.replace('[', '').replace(']', '')

        # Remove whitespace
        type_string = type_string.strip()

        # Filter out primitives
        primitives = {'int', 'long', 'short', 'byte', 'float', 'double', 'boolean', 'char', 'void'}
        if type_string.lower() in primitives:
            return ""

        # Filter out Java standard library (simple heuristic)
        java_stdlib = {'String', 'Integer', 'Long', 'Double', 'Boolean', 'Object', 'List', 'Map', 'Set'}
        if type_string in java_stdlib:
            return ""

        return type_string

    def _is_project_class(self, class_name: str, project_classes: List[str] = None) -> bool:
        """
        Check if a class name is a project class.

        Args:
            class_name: Class name to check
            project_classes: List of project class names (optional)

        Returns:
            True if it's a project class
        """
        if not class_name:
            return False

        # If we have a list of project classes, use it
        if project_classes is not None:
            return class_name in project_classes

        # Otherwise, assume any non-empty, non-primitive type is a project class
        return True

    def _class_depends_on(self, class_deps: ClassDependencies, target_class: str) -> bool:
        """
        Check if a class depends on a target class.

        Args:
            class_deps: ClassDependencies to check
            target_class: Target class name

        Returns:
            True if class_deps depends on target_class
        """
        # Check field types
        for field in class_deps.fields:
            if target_class in field.type:
                return True

        # Check method signatures
        for method in class_deps.get_all_methods():
            if target_class in method.return_type:
                return True

            for param in method.parameters:
                if target_class in param['type']:
                    return True

        return False

    def calculate_coupling_metrics(
        self,
        class_deps: ClassDependencies,
        all_class_deps: List[ClassDependencies] = None
    ) -> Dict[str, float]:
        """
        Calculate all coupling metrics.

        Args:
            class_deps: ClassDependencies object
            all_class_deps: List of all class dependencies (optional)

        Returns:
            Dictionary of metric names to values
        """
        metrics = {}

        # CBO
        if all_class_deps:
            all_class_names = [cd.class_name for cd in all_class_deps]
            metrics['cbo'] = self.calculate_cbo(class_deps, all_class_names)
        else:
            metrics['cbo'] = self.calculate_cbo(class_deps)

        # Instability (requires all_class_deps)
        if all_class_deps:
            metrics['instability'] = self.calculate_instability(
                class_deps.class_name,
                class_deps,
                all_class_deps
            )

        return metrics
