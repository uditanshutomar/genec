import javalang.parse
import pytest

from genec.parsers.java_parser import JavaParser


@pytest.fixture
def parser():
    return JavaParser()


def test_extract_method_calls_fallback(monkeypatch, parser):
    def raise_parse(_):
        raise Exception("forced failure")

    monkeypatch.setattr(javalang.parse, "parse", raise_parse)

    calls = parser.extract_method_calls("helper(); other(1); this.helper();")
    assert {"helper", "other"} <= calls


def test_extract_field_accesses_fallback(monkeypatch, parser):
    def raise_parse(_):
        raise Exception("forced failure")

    monkeypatch.setattr(javalang.parse, "parse", raise_parse)

    body = "total += SOME_FIELD + this.otherField + localVar;"
    fields = parser.extract_field_accesses(body)
    assert {"SOME_FIELD", "otherField"} <= fields
