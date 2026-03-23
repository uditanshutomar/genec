"""Tests for genec.parsers.java_parser.JavaParser."""

import pytest

from genec.parsers.java_parser import JavaParser, ParsedField, ParsedMethod


class TestParseFile:
    """Tests for parse_file and parse_file_content returning a javalang AST."""

    def test_parse_file_returns_compilation_unit(self, tmp_path):
        java_file = tmp_path / "Hello.java"
        java_file.write_text("public class Hello {}")
        parser = JavaParser()
        tree = parser.parse_file(str(java_file))
        assert tree is not None

    def test_parse_file_returns_none_for_invalid_syntax(self, tmp_path):
        java_file = tmp_path / "Bad.java"
        java_file.write_text("this is not java {{{{")
        parser = JavaParser()
        tree = parser.parse_file(str(java_file))
        assert tree is None

    def test_parse_file_content_returns_compilation_unit(self):
        parser = JavaParser()
        tree = parser.parse_file_content("public class Foo {}")
        assert tree is not None

    def test_parse_file_content_returns_none_for_garbage(self):
        parser = JavaParser()
        tree = parser.parse_file_content("not valid java }{")
        assert tree is None


class TestExtractClassInfo:
    """Tests for extract_class_info which is the main high-level API."""

    def _extract(self, source_code: str) -> dict | None:
        parser = JavaParser()
        return parser.extract_class_info(tree=None, source_code=source_code)

    # ── basic class ──────────────────────────────────────────────────────

    def test_simple_class_methods_and_fields(self):
        code = """\
package com.example;

public class SimpleClass {
    private int count;
    private String name;

    public int getCount() {
        return count;
    }

    public void setName(String name) {
        this.name = name;
    }

    public void process() {
        setName("test");
        int c = getCount();
    }
}
"""
        info = self._extract(code)
        assert info is not None
        assert info["class_name"] == "SimpleClass"
        assert info["package_name"] == "com.example"

        method_names = [m.name for m in info["methods"]]
        assert "getCount" in method_names
        assert "setName" in method_names
        assert "process" in method_names
        assert len(info["methods"]) == 3

        field_names = [f.name for f in info["fields"]]
        assert "count" in field_names
        assert "name" in field_names
        assert len(info["fields"]) == 2

    # ── empty class ──────────────────────────────────────────────────────

    def test_empty_class(self):
        info = self._extract("public class Empty {}")
        assert info is not None
        assert info["class_name"] == "Empty"
        assert len(info["methods"]) == 0
        assert len(info["fields"]) == 0
        assert len(info["constructors"]) == 0

    # ── class with only fields ───────────────────────────────────────────

    def test_class_with_only_fields(self):
        code = """\
public class OnlyFields {
    private int x;
    protected double y;
    public String z;
}
"""
        info = self._extract(code)
        assert info is not None
        field_names = {f.name for f in info["fields"]}
        assert field_names == {"x", "y", "z"}
        assert len(info["methods"]) == 0

    # ── constructor ──────────────────────────────────────────────────────

    def test_class_with_constructor(self):
        code = """\
public class WithCtor {
    private int x;

    public WithCtor(int x) {
        this.x = x;
    }

    public int getX() {
        return x;
    }
}
"""
        info = self._extract(code)
        assert info is not None
        assert len(info["constructors"]) == 1

        ctor = info["constructors"][0]
        assert ctor.is_constructor is True
        assert len(ctor.parameters) == 1
        assert ctor.parameters[0]["name"] == "x"

        method_names = [m.name for m in info["methods"]]
        assert "getX" in method_names

    # ── method parameters ────────────────────────────────────────────────

    def test_method_with_multiple_parameters(self):
        code = """\
public class Params {
    public int add(int a, int b) {
        return a + b;
    }
}
"""
        info = self._extract(code)
        assert info is not None
        method = info["methods"][0]
        assert method.name == "add"
        assert len(method.parameters) == 2
        param_names = [p["name"] for p in method.parameters]
        assert "a" in param_names
        assert "b" in param_names

    # ── return types ─────────────────────────────────────────────────────

    def test_return_types(self):
        code = """\
public class ReturnTypes {
    public int intMethod() { return 0; }
    public String stringMethod() { return ""; }
    public void voidMethod() {}
}
"""
        info = self._extract(code)
        assert info is not None
        by_name = {m.name: m for m in info["methods"]}
        assert by_name["intMethod"].return_type == "int"
        assert by_name["stringMethod"].return_type == "String"
        assert by_name["voidMethod"].return_type == "void"

    # ── extends / implements ─────────────────────────────────────────────

    def test_extends_and_implements(self):
        code = """\
package org.test;

public class Child extends Parent implements Runnable, Serializable {
    public void run() {}
}
"""
        info = self._extract(code)
        assert info is not None
        assert info["extends"] == "Parent"
        assert "Runnable" in info["implements"]
        assert "Serializable" in info["implements"]

    # ── inner class (parser should grab outermost) ───────────────────────

    def test_inner_class_not_confused_with_outer(self):
        code = """\
public class Outer {
    private int a;

    public void doStuff() {}

    class Inner {
        private int b;
        public void innerMethod() {}
    }
}
"""
        info = self._extract(code)
        assert info is not None
        # The top-level extraction should be for Outer
        assert info["class_name"] == "Outer"

    # ── modifiers ────────────────────────────────────────────────────────

    def test_field_modifiers(self):
        code = """\
public class Mods {
    private static final int CONST = 42;
}
"""
        info = self._extract(code)
        assert info is not None
        f = info["fields"][0]
        assert f.name == "CONST"
        # Modifiers should include private, static, final in some form
        modifier_strs = [str(m) for m in f.modifiers]
        assert any("static" in m for m in modifier_strs)


class TestExtractMethodCalls:
    """Tests for extract_method_calls on method body strings."""

    def setup_method(self):
        self.parser = JavaParser()

    def test_simple_method_calls(self):
        body = 'setName("hello"); int x = getCount();'
        calls = self.parser.extract_method_calls(body)
        assert "setName" in calls
        assert "getCount" in calls

    def test_no_method_calls(self):
        body = "int x = 5; x = x + 1;"
        calls = self.parser.extract_method_calls(body)
        # Should not contain java keywords
        assert "if" not in calls
        assert "for" not in calls

    def test_chained_calls(self):
        body = 'list.add("item"); map.get("key");'
        calls = self.parser.extract_method_calls(body)
        assert "add" in calls
        assert "get" in calls

    def test_keywords_excluded(self):
        body = "if (x > 0) { return new Foo(); }"
        calls = self.parser.extract_method_calls(body)
        for kw in ("if", "return", "new"):
            assert kw not in calls


class TestExtractMethodCallsWithArity:
    """Tests for extract_method_calls_with_arity."""

    def setup_method(self):
        self.parser = JavaParser()

    def test_returns_tuples(self):
        body = 'foo(1, 2); bar("hello");'
        calls = self.parser.extract_method_calls_with_arity(body)
        assert len(calls) >= 2
        call_names = [c[0] for c in calls]
        assert "foo" in call_names
        assert "bar" in call_names

    def test_no_arg_call(self):
        body = "doSomething();"
        calls = self.parser.extract_method_calls_with_arity(body)
        assert len(calls) >= 1
        match = [c for c in calls if c[0] == "doSomething"]
        assert len(match) == 1
        assert match[0][1] == 0


class TestExtractFieldAccesses:
    """Tests for extract_field_accesses."""

    def setup_method(self):
        self.parser = JavaParser()

    def test_field_access_via_this(self):
        body = "this.count = 5; this.name = null;"
        fields = self.parser.extract_field_accesses(body)
        assert "count" in fields
        assert "name" in fields

    def test_simple_identifiers_included(self):
        body = "x = y + z;"
        fields = self.parser.extract_field_accesses(body)
        assert "x" in fields
        assert "y" in fields
        assert "z" in fields


class TestBuildSignature:
    """Tests for the _build_signature helper."""

    def test_no_params(self):
        parser = JavaParser()
        sig = parser._build_signature("foo", [])
        assert sig == "foo()"

    def test_with_params(self):
        parser = JavaParser()
        params = [{"name": "a", "type": "int"}, {"name": "b", "type": "String"}]
        sig = parser._build_signature("bar", params)
        assert sig == "bar(int,String)"


class TestFindMethodEndLine:
    """Tests for _find_method_end_line brace counting."""

    def test_simple_method(self):
        parser = JavaParser()
        lines = [
            "public void foo() {",  # line 1
            "    int x = 0;",       # line 2
            "}",                    # line 3
        ]
        end = parser._find_method_end_line(lines, 1)
        assert end == 3

    def test_nested_braces(self):
        parser = JavaParser()
        lines = [
            "public void foo() {",      # line 1
            "    if (true) {",           # line 2
            "        x = 1;",            # line 3
            "    }",                     # line 4
            "}",                         # line 5
        ]
        end = parser._find_method_end_line(lines, 1)
        assert end == 5


class TestParsedMethodFullSignature:
    """Tests for the ParsedMethod.full_signature() helper."""

    def test_regular_method(self):
        m = ParsedMethod(
            name="getX",
            signature="getX()",
            return_type="int",
            modifiers=["public"],
            parameters=[],
            start_line=1,
            end_line=3,
            body="return x;",
        )
        assert m.full_signature() == "int getX()"

    def test_constructor(self):
        m = ParsedMethod(
            name="Foo",
            signature="<init>(int)",
            return_type="",
            modifiers=["public"],
            parameters=[{"name": "x", "type": "int"}],
            start_line=1,
            end_line=3,
            body="this.x = x;",
            is_constructor=True,
        )
        assert m.full_signature() == "Foo(int x)"

    def test_multiple_params(self):
        m = ParsedMethod(
            name="add",
            signature="add(int,int)",
            return_type="int",
            modifiers=["public"],
            parameters=[
                {"name": "a", "type": "int"},
                {"name": "b", "type": "int"},
            ],
            start_line=1,
            end_line=3,
            body="return a+b;",
        )
        assert m.full_signature() == "int add(int a, int b)"


class TestParseFileFromDisk:
    """Tests that exercise parse_file with actual temp files."""

    def test_parse_file_then_extract(self, tmp_path):
        code = """\
package demo;

public class Demo {
    private int value;

    public Demo(int v) {
        this.value = v;
    }

    public int getValue() {
        return value;
    }
}
"""
        f = tmp_path / "Demo.java"
        f.write_text(code)

        parser = JavaParser()
        tree = parser.parse_file(str(f))
        assert tree is not None

        info = parser.extract_class_info(tree, code)
        assert info is not None
        assert info["class_name"] == "Demo"
        assert info["package_name"] == "demo"
        assert len(info["fields"]) == 1
        assert info["fields"][0].name == "value"
