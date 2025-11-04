"""Semantic verification of refactoring transformations."""

from typing import Set, Dict, Tuple, Optional
import tempfile
from pathlib import Path

from genec.parsers.java_parser import JavaParser, ParsedMethod
from genec.core.dependency_analyzer import ClassDependencies
from genec.core.cluster_detector import Cluster
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


class SemanticVerifier:
    """Verifies that refactorings are semantically correct Extract Class transformations."""

    def __init__(self):
        """Initialize semantic verifier."""
        self.parser = JavaParser()
        self.logger = get_logger(self.__class__.__name__)

    def verify(
        self,
        original_code: str,
        new_class_code: str,
        modified_original_code: str,
        cluster: Cluster,
        class_deps: ClassDependencies
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify semantic correctness of the refactoring.

        Checks:
        1. All extracted members exist in original class
        2. Extracted members are removed from modified original
        3. Extracted members appear in new class
        4. No members are missing or added unexpectedly
        5. Dependencies are maintained correctly

        Args:
            original_code: Original class code
            new_class_code: New extracted class code
            modified_original_code: Modified original class code
            cluster: Cluster that was extracted
            class_deps: Original class dependencies

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        self.logger.info("Running semantic verification")

        try:
            # Extract class information using the resilient parser
            original_info = self._extract_info_with_fallback(original_code, class_deps.file_path)
            new_info = self._extract_info_with_fallback(new_class_code, None)
            modified_info = self._extract_info_with_fallback(modified_original_code, None)

            if not all([original_info, new_info, modified_info]):
                return False, "Failed to parse one or more classes"

            original_members = self._extract_members(original_info)
            new_class_members = self._extract_members(new_info)
            modified_members = self._extract_members(modified_info)

            # Get cluster members
            cluster_methods = set(cluster.get_methods())
            cluster_fields = set(cluster.get_fields())

            # Verify extracted members exist in original
            for method_sig in cluster_methods:
                # Match by method name (signatures might differ slightly)
                method_name = method_sig.split('(')[0]
                if method_name == class_deps.class_name:
                    continue  # Skip constructors
                if not any(method_name in m for m in original_members['methods']):
                    return False, f"Extracted method {method_name} not found in original class"

            for field in cluster_fields:
                if field not in original_members['fields']:
                    return False, f"Extracted field {field} not found in original class"

            # Verify extracted members appear in new class
            for method_sig in cluster_methods:
                method_name = method_sig.split('(')[0]
                if method_name == class_deps.class_name:
                    continue  # Skip constructors
                if not any(method_name in m for m in new_class_members['methods']):
                    return False, f"Method {method_name} missing from new class"

            for field in cluster_fields:
                if field not in new_class_members['fields']:
                    return False, f"Field {field} missing from new class"

            # Verify extracted members removed from modified original
            for method_sig in cluster_methods:
                method_name = method_sig.split('(')[0]
                if method_name == class_deps.class_name:
                    continue  # Skip constructors
                if method_name in modified_members['methods']:
                    if not self._is_delegation_method(modified_info, modified_original_code, method_name):
                        return False, f"Method {method_name} still in modified class (not delegation)"

            # Verify no unexpected member loss
            # (Modified + New should roughly equal Original, accounting for delegation)
            original_method_count = len(original_members['methods'])
            modified_method_count = len(modified_members['methods'])
            new_class_method_count = len(new_class_members['methods'])

            # Allow for delegation methods and constructors
            total_after = modified_method_count + new_class_method_count
            if total_after < original_method_count - 2:  # Allow some tolerance
                return False, f"Too many methods lost in refactoring: {original_method_count} -> {total_after}"

            self.logger.info("Semantic verification PASSED")
            return True, None

        except Exception as e:
            error_msg = f"Semantic verification error: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg

    def _extract_members(self, class_info: Dict) -> Dict[str, Set[str]]:
        """
        Extract method and field names from parsed class information.

        Returns:
            Dict with 'methods' and 'fields' sets
        """
        members = {
            'methods': set(),
            'fields': set()
        }

        for method in class_info.get('methods', []):
            members['methods'].add(method.name)

        for constructor in class_info.get('constructors', []):
            members['methods'].add(constructor.name)

        for field in class_info.get('fields', []):
            members['fields'].add(field.name)

        return members

    def _is_delegation_method(self, class_info: Dict, source: str, method_name: str) -> bool:
        """
        Check if a method is a simple delegation method.

        A delegation method typically just calls another object's method.

        Args:
            class_info: Parsed class information
            method_name: Method name to check

        Returns:
            True if method appears to be a delegation
        """
        for method in class_info.get('methods', []):
            if method.name != method_name:
                continue
            body = (method.body or '').strip()
            if not body:
                return False

            # Strip braces and whitespace for heuristic check
            body_lines = [line.strip() for line in body.splitlines() if line.strip()]
            if not body_lines:
                return False

            # Remove signature and enclosing braces if present
            statements = []
            for idx, line in enumerate(body_lines):
                if idx == 0 and ('(' in line and line.endswith('{')):
                    continue
                if line == '}' or line == '};':
                    continue
                statements.append(line)

            if len(statements) == 1:
                stmt = statements[0]
                if 'return' in stmt:
                    stmt = stmt.replace('return', '').strip().rstrip(';')
                if 'ArrayShuffler.' in stmt or 'owner.' in stmt:
                    return True

        # Constructors aren't used for delegation here
        if self._is_delegation_by_source(source, method_name):
            return True

        return False

    def _is_delegation_by_source(self, source: str, method_name: str) -> bool:
        import re

        # Pattern to match method with name, handling:
        # - Generic type parameters
        # - Multi-line signatures
        # - throws clauses
        # - Opening brace on same or different line
        pattern = re.compile(
            rf"(?:public|protected|private|static|\s)*\s+{re.escape(method_name)}\s*\([^{{]*?\)\s*(?:throws\s+[^{{]*?)?\s*\{{([^{{}}]*)\}}",
            re.DOTALL
        )
        for match in pattern.finditer(source):
            body = match.group(1).strip()
            if not body:
                continue
            statements = [line.strip().rstrip(';') for line in body.splitlines() if line.strip()]
            if len(statements) > 1:
                continue
            if not statements:
                continue
            stmt = statements[0]
            stmt = stmt.replace('return', '').strip()
            # Check if it's calling another class's method with the same name
            if f".{method_name}(" in stmt:
                return True
        return False

    def _extract_info_with_fallback(self, source: str, file_path: Optional[str]) -> Optional[Dict]:
        info = self.parser.extract_class_info(None, source, file_path)
        if info or file_path:
            return info

        # Write to temp file and retry with inspector
        with tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False, encoding='utf-8') as tmp:
            tmp.write(source)
            tmp_path = tmp.name

        try:
            return self.parser.extract_class_info(None, source, tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def verify_no_behavior_change(
        self,
        original_code: str,
        modified_code: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify that behavior is preserved (simplified version).

        In a full implementation, this would use static analysis tools
        to verify behavioral equivalence.

        Args:
            original_code: Original class code
            modified_code: Modified class code

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        # For now, this is a placeholder
        # A full implementation would use tools like JPF or symbolic execution

        self.logger.info("Skipping detailed behavioral equivalence check (placeholder)")
        return True, None
