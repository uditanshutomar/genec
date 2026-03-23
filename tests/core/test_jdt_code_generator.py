"""Unit tests for JDTCodeGenerator."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from genec.core.models import Cluster
from genec.core.dependency_analyzer import ClassDependencies, FieldInfo, MethodInfo
from genec.core.jdt_code_generator import (
    CodeGenerationError,
    GeneratedCode,
    JDTCodeGenerator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cluster(methods: dict[str, str] | None = None, fields: dict[str, str] | None = None, cluster_id: int = 0) -> Cluster:
    """Build a minimal Cluster with the given methods and fields."""
    member_types: dict[str, str] = {}
    if methods:
        member_types.update(methods)
    if fields:
        member_types.update(fields)
    return Cluster(
        id=cluster_id,
        member_names=list(member_types.keys()),
        member_types=member_types,
    )


def _make_class_deps(
    methods_info: list[MethodInfo] | None = None,
    field_accesses: dict[str, list[str]] | None = None,
    method_calls: dict[str, list[str]] | None = None,
) -> ClassDependencies:
    """Build a minimal ClassDependencies."""
    return ClassDependencies(
        class_name="Original",
        package_name="com.example",
        file_path="/tmp/Original.java",
        methods=methods_info or [],
        fields=[],
        method_calls=method_calls or {},
        field_accesses=field_accesses or {},
    )


def _make_method_info(name: str, signature: str | None = None, modifiers: list[str] | None = None, body: str = "") -> MethodInfo:
    sig = signature or f"{name}()"
    return MethodInfo(
        name=name,
        signature=sig,
        return_type="void",
        modifiers=modifiers or ["public"],
        parameters=[],
        start_line=1,
        end_line=10,
        body=body,
    )


def _generator_with_fake_jar(tmp_path: Path) -> JDTCodeGenerator:
    """Create a JDTCodeGenerator whose JAR path points at a real (empty) file."""
    jar = tmp_path / "fake.jar"
    jar.write_text("")
    return JDTCodeGenerator(jdt_wrapper_jar=str(jar), auto_download=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestJDTCodeGeneratorInit:
    """Tests for constructor / JAR discovery."""

    def test_raises_when_jar_not_found(self, tmp_path):
        """Should raise FileNotFoundError when JAR doesn't exist and auto_download is off."""
        with pytest.raises(FileNotFoundError, match="JDT wrapper JAR not found"):
            JDTCodeGenerator(
                jdt_wrapper_jar=str(tmp_path / "nonexistent.jar"),
                auto_download=False,
            )

    def test_accepts_existing_jar(self, tmp_path):
        """Should initialise successfully when JAR exists."""
        gen = _generator_with_fake_jar(tmp_path)
        assert gen.jdt_wrapper_jar.endswith("fake.jar")

    def test_custom_timeout(self, tmp_path):
        jar = tmp_path / "fake.jar"
        jar.write_text("")
        gen = JDTCodeGenerator(jdt_wrapper_jar=str(jar), timeout=120, auto_download=False)
        assert gen.timeout == 120

    @patch("genec.core.jdt_code_generator.os.path.exists", return_value=False)
    def test_auto_download_attempted_when_jar_missing(self, mock_exists, tmp_path):
        """When auto_download=True and JAR missing, _download_jdt_wrapper is called."""
        with patch.object(JDTCodeGenerator, "_download_jdt_wrapper") as mock_dl:
            with pytest.raises(FileNotFoundError):
                JDTCodeGenerator(jdt_wrapper_jar=str(tmp_path / "x.jar"), auto_download=True)
            mock_dl.assert_called_once()


class TestSpecConstruction:
    """Tests for spec building inside generate()."""

    def test_constructs_valid_spec(self, tmp_path):
        """Should build a spec dict with projectPath, classFile, newClassName, methods, fields."""
        gen = _generator_with_fake_jar(tmp_path)

        cluster = _make_cluster(
            methods={"doWork()": "method", "process(int)": "method"},
            fields={"count": "field"},
        )
        class_deps = _make_class_deps(
            methods_info=[
                _make_method_info("doWork", "doWork()"),
                _make_method_info("process", "process(int)"),
            ],
        )

        # Capture the spec passed to _call_jdt_wrapper
        captured = {}

        def fake_call(spec):
            captured.update(spec)
            return {"success": True, "newClassCode": "class X{}", "modifiedOriginalCode": "class Y{}"}

        gen._call_jdt_wrapper = fake_call

        gen.generate(
            cluster=cluster,
            new_class_name="WorkProcessor",
            class_file="/repo/src/Original.java",
            repo_path="/repo",
            class_deps=class_deps,
        )

        assert captured["projectPath"] == "/repo"
        assert captured["classFile"] == "/repo/src/Original.java"
        assert captured["newClassName"] == "WorkProcessor"
        assert isinstance(captured["methods"], list)
        assert isinstance(captured["fields"], list)


class TestClassNameValidation:
    """Tests for new class name validation."""

    @pytest.mark.parametrize("bad_name", ["", "123abc", None])
    def test_rejects_invalid_class_names(self, bad_name, tmp_path):
        """Should raise CodeGenerationError for invalid Java class names."""
        gen = _generator_with_fake_jar(tmp_path)
        cluster = _make_cluster(methods={"foo()": "method"})
        class_deps = _make_class_deps(
            methods_info=[_make_method_info("foo", "foo()")],
        )
        with pytest.raises(CodeGenerationError, match="Invalid new class name"):
            gen.generate(
                cluster=cluster,
                new_class_name=bad_name,
                class_file="/repo/Original.java",
                repo_path="/repo",
                class_deps=class_deps,
            )

    def test_accepts_valid_class_name(self, tmp_path):
        gen = _generator_with_fake_jar(tmp_path)
        cluster = _make_cluster(methods={"run()": "method"})
        class_deps = _make_class_deps(
            methods_info=[_make_method_info("run", "run()")],
        )
        gen._call_jdt_wrapper = lambda spec: {
            "success": True,
            "newClassCode": "class A{}",
            "modifiedOriginalCode": "class B{}",
        }
        result = gen.generate(
            cluster=cluster,
            new_class_name="ValidName",
            class_file="/repo/X.java",
            repo_path="/repo",
            class_deps=class_deps,
        )
        assert isinstance(result, GeneratedCode)


class TestFieldInference:
    """Tests for _infer_fields."""

    def test_infers_exclusive_fields(self, tmp_path):
        """Should return only fields exclusively used by cluster methods."""
        gen = _generator_with_fake_jar(tmp_path)
        cluster = _make_cluster(methods={"foo()": "method"})
        class_deps = _make_class_deps(
            field_accesses={
                "foo()": ["exclusiveField", "sharedField"],
                "bar()": ["sharedField"],  # non-cluster method uses sharedField
            },
        )
        result = gen._infer_fields(cluster, class_deps)
        assert "exclusiveField" in result
        assert "sharedField" not in result

    def test_returns_empty_when_no_fields_accessed(self, tmp_path):
        gen = _generator_with_fake_jar(tmp_path)
        cluster = _make_cluster(methods={"foo()": "method"})
        class_deps = _make_class_deps(field_accesses={})
        assert gen._infer_fields(cluster, class_deps) == []


class TestHelperMethodAugmentation:
    """Tests for _augment_methods."""

    def test_adds_private_helpers(self, tmp_path):
        """Should include private methods called by cluster methods."""
        gen = _generator_with_fake_jar(tmp_path)
        cluster = _make_cluster(methods={"doWork()": "method"})
        class_deps = _make_class_deps(
            methods_info=[
                _make_method_info("doWork", "doWork()", modifiers=["public"]),
                _make_method_info("helper", "helper()", modifiers=["private"]),
            ],
            method_calls={"doWork()": ["helper()"]},
        )
        result = gen._augment_methods(cluster, class_deps)
        assert "helper()" in result

    def test_does_not_add_public_methods(self, tmp_path):
        """Should NOT add public non-static methods that are not overloads."""
        gen = _generator_with_fake_jar(tmp_path)
        cluster = _make_cluster(methods={"doWork()": "method"})
        class_deps = _make_class_deps(
            methods_info=[
                _make_method_info("doWork", "doWork()", modifiers=["public"]),
                _make_method_info("publicHelper", "publicHelper()", modifiers=["public"]),
            ],
            method_calls={"doWork()": ["publicHelper()"]},
        )
        result = gen._augment_methods(cluster, class_deps)
        assert "publicHelper()" not in result


class TestFilterAccessors:
    """Tests for _filter_accessors."""

    def test_filters_getter_setter(self, tmp_path):
        gen = _generator_with_fake_jar(tmp_path)
        methods = ["getName()", "setName(String)", "compute()"]
        fields = ["name"]
        result = gen._filter_accessors(methods, fields)
        assert "compute()" in result
        assert "getName()" not in result
        assert "setName(String)" not in result

    def test_no_filtering_without_fields(self, tmp_path):
        gen = _generator_with_fake_jar(tmp_path)
        methods = ["getName()", "compute()"]
        assert gen._filter_accessors(methods, []) == methods


class TestJARExecution:
    """Tests for _call_jdt_wrapper and generate integration with subprocess."""

    def test_parses_successful_jar_output(self, tmp_path):
        """Should parse JSON response from JAR on success."""
        gen = _generator_with_fake_jar(tmp_path)
        expected_output = {
            "success": True,
            "newClassCode": "public class Extracted {}",
            "modifiedOriginalCode": "public class Original {}",
            "message": "Refactoring completed",
        }

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(expected_output)

        with patch("genec.core.jdt_code_generator.subprocess.run", return_value=mock_result):
            result = gen._call_jdt_wrapper({"test": True})

        assert result["success"] is True
        assert result["newClassCode"] == "public class Extracted {}"

    def test_handles_jar_nonzero_exit_with_json_stderr(self, tmp_path):
        gen = _generator_with_fake_jar(tmp_path)
        error_json = {"success": False, "message": "Type mismatch"}
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = json.dumps(error_json)

        with patch("genec.core.jdt_code_generator.subprocess.run", return_value=mock_result):
            result = gen._call_jdt_wrapper({})

        assert result["success"] is False
        assert result["message"] == "Type mismatch"

    def test_handles_jar_nonzero_exit_with_non_json_stderr(self, tmp_path):
        gen = _generator_with_fake_jar(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "NullPointerException at line 42"

        with patch("genec.core.jdt_code_generator.subprocess.run", return_value=mock_result):
            with pytest.raises(CodeGenerationError, match="exit code 1"):
                gen._call_jdt_wrapper({})

    def test_handles_timeout(self, tmp_path):
        gen = _generator_with_fake_jar(tmp_path)
        with patch(
            "genec.core.jdt_code_generator.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="java", timeout=60),
        ):
            with pytest.raises(CodeGenerationError, match="timed out"):
                gen._call_jdt_wrapper({})

    def test_handles_java_not_found(self, tmp_path):
        gen = _generator_with_fake_jar(tmp_path)
        with patch(
            "genec.core.jdt_code_generator.subprocess.run",
            side_effect=FileNotFoundError("java not found"),
        ):
            with pytest.raises(CodeGenerationError, match="Java runtime not found"):
                gen._call_jdt_wrapper({})


class TestGenerateEndToEnd:
    """Integration-style tests for the full generate() flow with mocked subprocess."""

    def test_generate_returns_generated_code(self, tmp_path):
        gen = _generator_with_fake_jar(tmp_path)
        cluster = _make_cluster(methods={"process()": "method"})
        class_deps = _make_class_deps(
            methods_info=[_make_method_info("process", "process()")],
        )

        jar_output = {
            "success": True,
            "newClassCode": "public class Processor { void process() {} }",
            "modifiedOriginalCode": "public class Original { Processor p; }",
            "message": "OK",
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(jar_output)

        with patch("genec.core.jdt_code_generator.subprocess.run", return_value=mock_result):
            result = gen.generate(
                cluster=cluster,
                new_class_name="Processor",
                class_file="/repo/Original.java",
                repo_path="/repo",
                class_deps=class_deps,
            )

        assert isinstance(result, GeneratedCode)
        assert "Processor" in result.new_class_code
        assert "Original" in result.modified_original_code

    def test_generate_raises_on_jdt_failure(self, tmp_path):
        gen = _generator_with_fake_jar(tmp_path)
        cluster = _make_cluster(methods={"x()": "method"})
        class_deps = _make_class_deps(
            methods_info=[_make_method_info("x", "x()")],
        )

        gen._call_jdt_wrapper = lambda spec: {"success": False, "message": "Compilation error"}

        with pytest.raises(CodeGenerationError, match="Compilation error"):
            gen.generate(
                cluster=cluster,
                new_class_name="Extracted",
                class_file="/repo/X.java",
                repo_path="/repo",
                class_deps=class_deps,
            )

    def test_generate_raises_when_no_methods(self, tmp_path):
        """Cluster with only fields and no methods should be rejected."""
        gen = _generator_with_fake_jar(tmp_path)
        cluster = _make_cluster(fields={"count": "field"})
        class_deps = _make_class_deps()

        with pytest.raises(CodeGenerationError, match="at least one method"):
            gen.generate(
                cluster=cluster,
                new_class_name="FieldOnly",
                class_file="/repo/X.java",
                repo_path="/repo",
                class_deps=class_deps,
            )


class TestIsAvailable:
    def test_is_available_true(self, tmp_path):
        gen = _generator_with_fake_jar(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("genec.core.jdt_code_generator.subprocess.run", return_value=mock_result):
            assert gen.is_available() is True

    def test_is_available_false_no_java(self, tmp_path):
        gen = _generator_with_fake_jar(tmp_path)
        with patch(
            "genec.core.jdt_code_generator.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            assert gen.is_available() is False
