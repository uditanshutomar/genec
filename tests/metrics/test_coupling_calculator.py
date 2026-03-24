"""Tests for genec.metrics.coupling_calculator.CouplingCalculator."""

import pytest
from unittest.mock import patch, MagicMock

from genec.core.dependency_analyzer import ClassDependencies, MethodInfo, FieldInfo
from genec.metrics.coupling_calculator import CouplingCalculator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _method(
    name: str,
    return_type: str = "void",
    params: list[dict] | None = None,
) -> MethodInfo:
    return MethodInfo(
        name=name,
        signature=f"{name}()",
        return_type=return_type,
        modifiers=["public"],
        parameters=params or [],
        start_line=1,
        end_line=10,
        body="",
    )


def _field(name: str, ftype: str = "int") -> FieldInfo:
    return FieldInfo(name=name, type=ftype, modifiers=["private"], line_number=1)


def _make_deps(
    class_name: str = "MyClass",
    methods: list[MethodInfo] | None = None,
    fields: list[FieldInfo] | None = None,
) -> ClassDependencies:
    return ClassDependencies(
        class_name=class_name,
        package_name="com.test",
        file_path=f"/tmp/{class_name}.java",
        methods=methods or [],
        fields=fields or [],
        constructors=[],
    )


# ---------------------------------------------------------------------------
# TestCBO
# ---------------------------------------------------------------------------

class TestCBO:
    def test_zero_coupling_primitive_types_only(self):
        """Class with only primitive fields and void methods -> CBO = 0."""
        deps = _make_deps(
            methods=[_method("process", return_type="void")],
            fields=[_field("count", "int"), _field("flag", "boolean")],
        )

        calc = CouplingCalculator()
        cbo = calc.calculate_cbo(deps)

        assert cbo == 0

    def test_coupling_via_field_type(self):
        """Field of a project class type should contribute to CBO."""
        deps = _make_deps(
            methods=[],
            fields=[_field("helper", "HelperService")],
        )

        calc = CouplingCalculator()
        cbo = calc.calculate_cbo(deps, project_classes=["HelperService"])

        assert cbo == 1

    def test_coupling_via_return_type(self):
        """Method returning a project class type should contribute to CBO."""
        deps = _make_deps(
            methods=[_method("getResult", return_type="ResultObj")],
            fields=[],
        )

        calc = CouplingCalculator()
        cbo = calc.calculate_cbo(deps, project_classes=["ResultObj"])

        assert cbo == 1

    def test_coupling_via_parameter_type(self):
        """Method parameter of a project class type should contribute to CBO."""
        m = _method("process")
        m.parameters = [{"type": "InputData", "name": "data"}]
        deps = _make_deps(methods=[m], fields=[])

        calc = CouplingCalculator()
        cbo = calc.calculate_cbo(deps, project_classes=["InputData"])

        assert cbo == 1

    def test_self_reference_excluded(self):
        """References to the class itself should not count as coupling."""
        deps = _make_deps(
            class_name="MyClass",
            methods=[_method("clone", return_type="MyClass")],
            fields=[],
        )

        calc = CouplingCalculator()
        cbo = calc.calculate_cbo(deps, project_classes=["MyClass"])

        assert cbo == 0

    def test_multiple_coupling_sources(self):
        """Multiple coupled classes from fields, returns, and params."""
        m = _method("transform", return_type="OutputData")
        m.parameters = [{"type": "InputData", "name": "input"}]
        deps = _make_deps(
            methods=[m],
            fields=[_field("repo", "Repository")],
        )

        calc = CouplingCalculator()
        cbo = calc.calculate_cbo(
            deps, project_classes=["OutputData", "InputData", "Repository"]
        )

        assert cbo == 3

    def test_stdlib_types_excluded(self):
        """Java standard library types (String, List, etc.) should not count."""
        deps = _make_deps(
            methods=[_method("getName", return_type="String")],
            fields=[_field("items", "List")],
        )

        calc = CouplingCalculator()
        cbo = calc.calculate_cbo(deps)

        assert cbo == 0

    def test_generic_type_extracts_base(self):
        """Generic types like List<Foo> should extract 'List' (stdlib, excluded)."""
        deps = _make_deps(
            fields=[_field("items", "List<CustomItem>")],
        )

        calc = CouplingCalculator()
        # "List" is stdlib -> excluded; "CustomItem" inside generics is stripped
        # _extract_base_type strips everything after '<'
        cbo = calc.calculate_cbo(deps)

        assert cbo == 0  # Only "List" is extracted, which is stdlib

    def test_no_project_classes_list_counts_non_stdlib(self):
        """Without project_classes, count all non-primitive non-stdlib types."""
        deps = _make_deps(
            fields=[_field("service", "CustomService")],
        )

        calc = CouplingCalculator()
        cbo = calc.calculate_cbo(deps, project_classes=None)

        # Without explicit project list, non-stdlib types are counted
        assert cbo == 1  # CustomService is not a stdlib type


# ---------------------------------------------------------------------------
# TestAfferentCoupling
# ---------------------------------------------------------------------------

class TestAfferentCoupling:
    def test_no_dependents(self):
        """No other class depends on target -> Ca = 0."""
        calc = CouplingCalculator()
        target_deps = _make_deps(class_name="Target")
        other_deps = _make_deps(class_name="Other", fields=[_field("x", "int")])

        ca = calc.calculate_afferent_coupling("Target", [target_deps, other_deps])

        assert ca == 0

    def test_one_dependent(self):
        """One class has a field of target type -> Ca = 1."""
        calc = CouplingCalculator()
        target_deps = _make_deps(class_name="Target")
        dep_deps = _make_deps(
            class_name="Dependent",
            fields=[_field("ref", "Target")],
        )

        ca = calc.calculate_afferent_coupling("Target", [target_deps, dep_deps])

        assert ca == 1


# ---------------------------------------------------------------------------
# TestCouplingMetrics
# ---------------------------------------------------------------------------

class TestCouplingMetrics:
    def test_returns_cbo_key(self):
        """calculate_coupling_metrics should always return cbo."""
        deps = _make_deps(fields=[_field("x", "int")])

        calc = CouplingCalculator()
        metrics = calc.calculate_coupling_metrics(deps)

        assert "cbo" in metrics
        assert metrics["cbo"] == 0

    def test_returns_instability_when_all_deps_given(self):
        """With all_class_deps, instability should also be computed."""
        deps = _make_deps(class_name="A")
        other = _make_deps(class_name="B")

        calc = CouplingCalculator()
        metrics = calc.calculate_coupling_metrics(deps, all_class_deps=[deps, other])

        assert "instability" in metrics
        assert 0.0 <= metrics["instability"] <= 1.0


# ---------------------------------------------------------------------------
# TestExtractBaseType (internal helper, but worth testing)
# ---------------------------------------------------------------------------

class TestExtractBaseType:
    def test_primitive_returns_empty(self):
        calc = CouplingCalculator()
        assert calc._extract_base_type("int") == ""
        assert calc._extract_base_type("boolean") == ""
        assert calc._extract_base_type("void") == ""

    def test_stdlib_returns_empty(self):
        calc = CouplingCalculator()
        assert calc._extract_base_type("String") == ""
        assert calc._extract_base_type("List") == ""
        assert calc._extract_base_type("Map") == ""

    def test_custom_type_returned(self):
        calc = CouplingCalculator()
        assert calc._extract_base_type("MyService") == "MyService"

    def test_generic_stripped(self):
        calc = CouplingCalculator()
        assert calc._extract_base_type("List<Foo>") == ""  # List is stdlib

    def test_array_stripped(self):
        calc = CouplingCalculator()
        assert calc._extract_base_type("int[]") == ""  # primitive

    def test_empty_string(self):
        calc = CouplingCalculator()
        assert calc._extract_base_type("") == ""

    def test_none_input(self):
        calc = CouplingCalculator()
        assert calc._extract_base_type(None) == ""
