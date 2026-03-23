"""Tests for the SyntacticVerifier class."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from genec.verification.syntactic_verifier import SyntacticVerifier


class TestSyntacticVerifier:
    """Tests for SyntacticVerifier.verify()."""

    def _make_verifier(self, **kwargs):
        """Create a SyntacticVerifier without repo_path to avoid filesystem scanning."""
        defaults = {"java_compiler": "javac", "repo_path": None, "lenient_mode": True}
        defaults.update(kwargs)
        return SyntacticVerifier(**defaults)

    # ── verify() ──────────────────────────────────────────────────────────

    @patch("genec.verification.syntactic_verifier.subprocess.run")
    def test_valid_java_passes(self, mock_run):
        """Well-formed Java code should pass syntactic verification."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        verifier = self._make_verifier()
        new_class = (
            "public class ExtractedHelper {\n"
            "    private int count;\n"
            "    public int getCount() { return count; }\n"
            "}\n"
        )
        modified_original = (
            "public class Original {\n"
            "    private ExtractedHelper helper;\n"
            "    public void doWork() { helper.getCount(); }\n"
            "}\n"
        )

        success, error = verifier.verify(new_class, modified_original)

        assert success is True
        assert error is None
        mock_run.assert_called_once()
        # The command should include javac and both files
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "javac"

    @patch("genec.verification.syntactic_verifier.subprocess.run")
    def test_invalid_java_fails(self, mock_run):
        """Malformed Java should fail with error details."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Original.java:2: error: ';' expected\n    public void broken(\n                      ^\n1 error\n",
            stdout="",
        )

        verifier = self._make_verifier(lenient_mode=False)
        new_class = (
            "public class ExtractedHelper {\n"
            "    public void helper() {}\n"
            "}\n"
        )
        modified_original = (
            "public class Original {\n"
            "    public void broken(\n"  # missing closing paren and body
            "}\n"
        )

        success, error = verifier.verify(new_class, modified_original)

        assert success is False
        assert error is not None
        assert "error" in error.lower()

    @patch("genec.verification.syntactic_verifier.subprocess.run")
    def test_lenient_mode_passes_symbol_errors(self, mock_run):
        """In lenient mode, 'cannot find symbol' errors should be treated as pass."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Original.java:5: error: cannot find symbol\n    SomeExternalClass x;\n                     ^\n1 error\n",
            stdout="",
        )

        verifier = self._make_verifier(lenient_mode=True)
        new_class = "public class Helper { public void run() {} }\n"
        modified_original = "public class Original { public void work() {} }\n"

        success, error = verifier.verify(new_class, modified_original)

        assert success is True
        assert error is None

    @patch("genec.verification.syntactic_verifier.subprocess.run")
    def test_lenient_mode_fails_real_syntax_errors(self, mock_run):
        """In lenient mode, genuine syntax errors should still fail."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Original.java:2: error: illegal start of expression\n    public void {\n               ^\n1 error\n",
            stdout="",
        )

        verifier = self._make_verifier(lenient_mode=True)
        new_class = "public class Helper { public void run() {} }\n"
        modified_original = "public class Original { public void { } }\n"

        success, error = verifier.verify(new_class, modified_original)

        assert success is False
        assert error is not None

    @patch("genec.verification.syntactic_verifier.subprocess.run")
    def test_handles_missing_javac(self, mock_run):
        """Should handle case where javac is not installed (strict mode)."""
        mock_run.side_effect = FileNotFoundError("javac not found")

        verifier = self._make_verifier(lenient_mode=False)
        new_class = "public class Helper { public void run() {} }\n"
        modified_original = "public class Original { public void work() {} }\n"

        success, error = verifier.verify(new_class, modified_original)

        assert success is False
        assert error is not None
        assert "not found" in error.lower()

    @patch("genec.verification.syntactic_verifier.subprocess.run")
    def test_handles_compilation_timeout(self, mock_run):
        """Should handle javac timeout gracefully (strict mode)."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="javac", timeout=30)

        verifier = self._make_verifier(lenient_mode=False)
        new_class = "public class Helper { public void run() {} }\n"
        modified_original = "public class Original { public void work() {} }\n"

        success, error = verifier.verify(new_class, modified_original)

        assert success is False
        assert error is not None
        assert "timeout" in error.lower()

    @patch("genec.verification.syntactic_verifier.subprocess.run")
    def test_verify_with_package_name(self, mock_run):
        """Should create package directory structure when package_name is provided."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        verifier = self._make_verifier()
        new_class = (
            "package com.example;\n"
            "public class Helper { public void run() {} }\n"
        )
        modified_original = (
            "package com.example;\n"
            "public class Original { public void work() {} }\n"
        )

        success, error = verifier.verify(new_class, modified_original, package_name="com.example")

        assert success is True
        assert error is None

    def test_verify_fails_when_class_name_not_extracted(self):
        """Should fail if class name cannot be extracted from code."""
        verifier = self._make_verifier()
        # Code without a valid class declaration
        new_class = "// just a comment\n"
        modified_original = "// another comment\n"

        success, error = verifier.verify(new_class, modified_original)

        assert success is False
        assert error is not None
        assert "class name" in error.lower()


class TestExtractClassName:
    """Tests for SyntacticVerifier._extract_class_name()."""

    def _make_verifier(self):
        return SyntacticVerifier(repo_path=None)

    def test_extract_simple_class(self):
        verifier = self._make_verifier()
        code = "public class MyClass { }"
        assert verifier._extract_class_name(code) == "MyClass"

    def test_extract_abstract_class(self):
        verifier = self._make_verifier()
        code = "public abstract class AbstractHandler { }"
        assert verifier._extract_class_name(code) == "AbstractHandler"

    def test_extract_class_with_package(self):
        verifier = self._make_verifier()
        code = "package com.example;\npublic class Foo { }"
        assert verifier._extract_class_name(code) == "Foo"

    def test_returns_none_for_no_class(self):
        verifier = self._make_verifier()
        code = "interface NotAClass { }"
        assert verifier._extract_class_name(code) is None

    def test_ignores_class_in_comments(self):
        verifier = self._make_verifier()
        code = "// class FakeClass\npublic class RealClass { }"
        assert verifier._extract_class_name(code) == "RealClass"


class TestGenerateStubs:
    """Tests for SyntacticVerifier._generate_stubs_for_missing_classes()."""

    def _make_verifier(self):
        return SyntacticVerifier(repo_path=None)

    def test_generates_stub_for_unknown_class(self):
        verifier = self._make_verifier()
        modified = "public class Foo { CustomService svc; }"
        new_class = "public class Bar { }"
        existing = {"Foo", "Bar"}

        stubs = verifier._generate_stubs_for_missing_classes(
            modified, new_class, "", existing
        )

        assert "CustomService" in stubs
        assert "public class CustomService" in stubs["CustomService"]

    def test_does_not_stub_java_builtins(self):
        verifier = self._make_verifier()
        modified = "public class Foo { String name; List<Integer> items; }"
        new_class = "public class Bar { }"
        existing = {"Foo", "Bar"}

        stubs = verifier._generate_stubs_for_missing_classes(
            modified, new_class, "", existing
        )

        assert "String" not in stubs
        assert "List" not in stubs
        assert "Integer" not in stubs

    def test_does_not_stub_existing_classes(self):
        verifier = self._make_verifier()
        modified = "public class Foo { Bar bar; }"
        new_class = "public class Bar { }"
        existing = {"Foo", "Bar"}

        stubs = verifier._generate_stubs_for_missing_classes(
            modified, new_class, "", existing
        )

        assert "Foo" not in stubs
        assert "Bar" not in stubs

    def test_stub_includes_package(self):
        verifier = self._make_verifier()
        modified = "public class Foo { CustomDao dao; }"
        new_class = "public class Bar { }"
        existing = {"Foo", "Bar"}

        stubs = verifier._generate_stubs_for_missing_classes(
            modified, new_class, "com.example", existing
        )

        assert "CustomDao" in stubs
        assert "package com.example;" in stubs["CustomDao"]


class TestCheckCompilerAvailable:
    """Tests for SyntacticVerifier.check_compiler_available()."""

    @patch("genec.verification.syntactic_verifier.subprocess.run")
    def test_returns_true_when_javac_exists(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        verifier = SyntacticVerifier(repo_path=None)
        assert verifier.check_compiler_available() is True

    @patch("genec.verification.syntactic_verifier.subprocess.run")
    def test_returns_false_when_javac_missing(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        verifier = SyntacticVerifier(repo_path=None)
        assert verifier.check_compiler_available() is False


class TestDetectBuildSystem:
    """Tests for SyntacticVerifier._detect_build_system()."""

    def test_detects_maven(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project/>")
        verifier = SyntacticVerifier(repo_path=str(tmp_path))
        assert verifier.build_system == "maven"

    def test_detects_gradle(self, tmp_path):
        (tmp_path / "build.gradle").write_text("apply plugin: 'java'")
        verifier = SyntacticVerifier(repo_path=str(tmp_path))
        assert verifier.build_system == "gradle"

    def test_no_build_system(self, tmp_path):
        verifier = SyntacticVerifier(repo_path=str(tmp_path))
        assert verifier.build_system is None
