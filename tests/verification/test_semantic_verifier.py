"""Tests for the SemanticVerifier class."""

from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest

from genec.core.models import Cluster
from genec.core.dependency_analyzer import ClassDependencies, FieldInfo, MethodInfo
from genec.verification.semantic_verifier import SemanticVerifier


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_parsed_method(name, signature=None, body=""):
    """Create a mock ParsedMethod-like object."""
    m = MagicMock()
    m.name = name
    m.signature = signature or f"{name}()"
    m.return_type = "void"
    m.modifiers = ["public"]
    m.parameters = []
    m.start_line = 1
    m.end_line = 10
    m.body = body
    return m


def _make_parsed_field(name, ftype="int"):
    """Create a mock ParsedField-like object."""
    f = MagicMock()
    f.name = name
    f.type = ftype
    f.modifiers = ["private"]
    f.line_number = 1
    return f


def _make_class_info(class_name, methods, fields, constructors=None):
    """Create a dict shaped like JavaParser.extract_class_info output."""
    return {
        "class_name": class_name,
        "package_name": "com.example",
        "methods": methods,
        "fields": fields,
        "constructors": constructors or [],
    }


def _make_cluster(methods, fields):
    """Create a Cluster with the given method signatures and field names."""
    member_names = list(methods) + list(fields)
    member_types = {}
    for m in methods:
        member_types[m] = "method"
    for f in fields:
        member_types[f] = "field"
    return Cluster(
        id=0,
        member_names=member_names,
        member_types=member_types,
    )


def _make_class_deps(class_name="Original", file_path="/fake/Original.java"):
    """Create a minimal ClassDependencies."""
    return ClassDependencies(
        class_name=class_name,
        package_name="com.example",
        file_path=file_path,
    )


class TestSemanticVerifier:
    """Tests for SemanticVerifier.verify()."""

    @patch.object(SemanticVerifier, "_extract_info_with_fallback")
    def test_all_members_moved(self, mock_extract):
        """All specified methods should be in new class."""
        # Original has: doWork, helper, count
        original_info = _make_class_info(
            "Original",
            methods=[_make_parsed_method("doWork"), _make_parsed_method("helper")],
            fields=[_make_parsed_field("count")],
        )
        # New class has the extracted members: helper, count
        new_info = _make_class_info(
            "ExtractedHelper",
            methods=[_make_parsed_method("helper")],
            fields=[_make_parsed_field("count")],
        )
        # Modified original keeps doWork, removes helper/count, adds delegation
        modified_info = _make_class_info(
            "Original",
            methods=[_make_parsed_method("doWork")],
            fields=[],
        )

        mock_extract.side_effect = [original_info, new_info, modified_info]

        cluster = _make_cluster(methods=["helper()"], fields=["count"])
        class_deps = _make_class_deps()

        verifier = SemanticVerifier()
        success, error = verifier.verify(
            original_code="...",
            new_class_code="...",
            modified_original_code="...",
            cluster=cluster,
            class_deps=class_deps,
        )

        assert success is True
        assert error is None

    @patch.object(SemanticVerifier, "_extract_info_with_fallback")
    def test_detects_missing_member(self, mock_extract):
        """Should detect when a specified method is NOT in extracted class."""
        original_info = _make_class_info(
            "Original",
            methods=[_make_parsed_method("doWork"), _make_parsed_method("helper")],
            fields=[_make_parsed_field("count")],
        )
        # New class is MISSING the 'helper' method
        new_info = _make_class_info(
            "ExtractedHelper",
            methods=[],
            fields=[_make_parsed_field("count")],
        )
        modified_info = _make_class_info(
            "Original",
            methods=[_make_parsed_method("doWork")],
            fields=[],
        )

        mock_extract.side_effect = [original_info, new_info, modified_info]

        cluster = _make_cluster(methods=["helper()"], fields=["count"])
        class_deps = _make_class_deps()

        verifier = SemanticVerifier()
        success, error = verifier.verify(
            original_code="...",
            new_class_code="...",
            modified_original_code="...",
            cluster=cluster,
            class_deps=class_deps,
        )

        assert success is False
        assert error is not None
        assert "helper" in error

    @patch.object(SemanticVerifier, "_extract_info_with_fallback")
    def test_detects_missing_field(self, mock_extract):
        """Should detect when a specified field is NOT in extracted class."""
        original_info = _make_class_info(
            "Original",
            methods=[_make_parsed_method("doWork")],
            fields=[_make_parsed_field("count"), _make_parsed_field("name")],
        )
        # New class has count but NOT name
        new_info = _make_class_info(
            "ExtractedHelper",
            methods=[],
            fields=[_make_parsed_field("count")],
        )
        modified_info = _make_class_info(
            "Original",
            methods=[_make_parsed_method("doWork")],
            fields=[],
        )

        mock_extract.side_effect = [original_info, new_info, modified_info]

        cluster = _make_cluster(methods=[], fields=["count", "name"])
        class_deps = _make_class_deps()

        verifier = SemanticVerifier()
        success, error = verifier.verify(
            original_code="...",
            new_class_code="...",
            modified_original_code="...",
            cluster=cluster,
            class_deps=class_deps,
        )

        assert success is False
        assert error is not None
        assert "name" in error

    @patch.object(SemanticVerifier, "_extract_info_with_fallback")
    def test_detects_method_not_in_original(self, mock_extract):
        """Should fail when cluster references a method not in the original class."""
        original_info = _make_class_info(
            "Original",
            methods=[_make_parsed_method("doWork")],
            fields=[],
        )
        new_info = _make_class_info("Extracted", methods=[], fields=[])
        modified_info = _make_class_info("Original", methods=[], fields=[])

        mock_extract.side_effect = [original_info, new_info, modified_info]

        # Cluster references 'nonExistent' which is not in original
        cluster = _make_cluster(methods=["nonExistent()"], fields=[])
        class_deps = _make_class_deps()

        verifier = SemanticVerifier()
        success, error = verifier.verify("...", "...", "...", cluster, class_deps)

        assert success is False
        assert "nonExistent" in error

    @patch.object(SemanticVerifier, "_extract_info_with_fallback")
    def test_parse_failure_returns_error(self, mock_extract):
        """Should return error when parsing any class fails."""
        mock_extract.side_effect = [None, None, None]

        cluster = _make_cluster(methods=["helper()"], fields=[])
        class_deps = _make_class_deps()

        verifier = SemanticVerifier()
        success, error = verifier.verify("...", "...", "...", cluster, class_deps)

        assert success is False
        assert error is not None
        assert "parse" in error.lower() or "Failed" in error

    @patch.object(SemanticVerifier, "_extract_info_with_fallback")
    def test_constructor_methods_are_skipped(self, mock_extract):
        """Constructor methods matching class name should be skipped in verification."""
        original_info = _make_class_info(
            "Original",
            methods=[_make_parsed_method("doWork")],
            fields=[],
            constructors=[_make_parsed_method("Original", signature="Original()")],
        )
        new_info = _make_class_info(
            "Extracted",
            methods=[_make_parsed_method("doWork")],
            fields=[],
        )
        modified_info = _make_class_info(
            "Original",
            methods=[],
            fields=[],
        )

        mock_extract.side_effect = [original_info, new_info, modified_info]

        # Cluster includes the constructor name -- should be skipped
        cluster = _make_cluster(methods=["Original()", "doWork()"], fields=[])
        class_deps = _make_class_deps(class_name="Original")

        verifier = SemanticVerifier()
        success, error = verifier.verify("...", "...", "...", cluster, class_deps)

        assert success is True
        assert error is None


class TestExtractMembers:
    """Tests for SemanticVerifier._extract_members()."""

    def test_extracts_methods_and_fields(self):
        verifier = SemanticVerifier()
        class_info = _make_class_info(
            "Foo",
            methods=[_make_parsed_method("alpha"), _make_parsed_method("beta")],
            fields=[_make_parsed_field("x"), _make_parsed_field("y")],
        )

        members = verifier._extract_members(class_info)

        assert "alpha" in members["methods"]
        assert "beta" in members["methods"]
        assert "x" in members["fields"]
        assert "y" in members["fields"]

    def test_includes_constructors_as_methods(self):
        verifier = SemanticVerifier()
        class_info = _make_class_info(
            "Foo",
            methods=[],
            fields=[],
            constructors=[_make_parsed_method("Foo")],
        )

        members = verifier._extract_members(class_info)

        assert "Foo" in members["methods"]


class TestVerifyNoBehaviorChange:
    """Tests for SemanticVerifier.verify_no_behavior_change() placeholder."""

    def test_always_passes(self):
        """The placeholder implementation should always return True."""
        verifier = SemanticVerifier()
        success, error = verifier.verify_no_behavior_change("class A {}", "class A {}")
        assert success is True
        assert error is None
