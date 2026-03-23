"""Tests for genec.core.llm_interface.LLMInterface."""

from unittest.mock import MagicMock, patch

import pytest

from genec.core.models import Cluster
from genec.core.dependency_analyzer import ClassDependencies, FieldInfo, MethodInfo
from genec.core.llm_interface import LLMInterface
from genec.core.models import RefactoringSuggestion


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_cluster(cluster_id: int = 0, methods=None, fields=None) -> Cluster:
    """Build a minimal Cluster for testing."""
    methods = methods or ["getX()", "setX(int)"]
    fields = fields or ["x"]
    member_names = methods + fields
    member_types = {m: "method" for m in methods}
    member_types.update({f: "field" for f in fields})
    return Cluster(
        id=cluster_id,
        member_names=member_names,
        member_types=member_types,
    )


def _make_class_deps(class_name: str = "OriginalClass") -> ClassDependencies:
    """Build a minimal ClassDependencies for testing."""
    return ClassDependencies(
        class_name=class_name,
        package_name="com.example",
        file_path="/tmp/OriginalClass.java",
        methods=[
            MethodInfo(
                name="getX",
                signature="getX()",
                return_type="int",
                modifiers=["public"],
                parameters=[],
                start_line=5,
                end_line=7,
                body="return x;",
            ),
            MethodInfo(
                name="setX",
                signature="setX(int)",
                return_type="void",
                modifiers=["public"],
                parameters=[{"name": "x", "type": "int"}],
                start_line=9,
                end_line=11,
                body="this.x = x;",
            ),
        ],
        fields=[
            FieldInfo(name="x", type="int", modifiers=["private"], line_number=3),
        ],
    )


# ── RefactoringSuggestion dataclass ──────────────────────────────────────────

class TestRefactoringSuggestion:
    def test_defaults(self):
        s = RefactoringSuggestion(
            cluster_id=0,
            proposed_class_name="Foo",
            rationale="test",
            new_class_code="",
            modified_original_code="",
        )
        assert s.confidence_score is None
        assert s.quality_tier is None
        assert s.quality_reasons == []


# ── _validate_class_name ─────────────────────────────────────────────────────

class TestValidateClassName:
    """Test hallucination-prevention class name validation."""

    def setup_method(self):
        # Patch the Anthropic client so we never need a real API key
        with patch("genec.core.llm_interface.AnthropicClientWrapper") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.enabled = False
            mock_cls.return_value = mock_instance
            self.llm = LLMInterface(api_key="fake", use_chunking=False, use_hybrid_mode=False)

    def test_valid_name(self):
        assert self.llm._validate_class_name("DataConverter") is True

    def test_rejects_lowercase_start(self):
        assert self.llm._validate_class_name("dataConverter") is False

    def test_rejects_too_short(self):
        assert self.llm._validate_class_name("Ab") is False

    def test_rejects_bare_generic(self):
        assert self.llm._validate_class_name("Helper") is False
        assert self.llm._validate_class_name("Utils") is False

    def test_allows_compound_generic(self):
        # "DataHelper" is not in bare_generic set, so it should pass
        assert self.llm._validate_class_name("DataHelper") is True

    def test_rejects_non_ascii(self):
        assert self.llm._validate_class_name("Daten\u00fcbersetzer") is False

    def test_rejects_invalid_characters(self):
        assert self.llm._validate_class_name("My-Class") is False
        assert self.llm._validate_class_name("My Class") is False


# ── _extract_xml_tag ─────────────────────────────────────────────────────────

class TestExtractXmlTag:
    def setup_method(self):
        with patch("genec.core.llm_interface.AnthropicClientWrapper") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.enabled = False
            mock_cls.return_value = mock_instance
            self.llm = LLMInterface(api_key="fake", use_chunking=False, use_hybrid_mode=False)

    def test_extracts_simple_tag(self):
        text = "<class_name>DataProcessor</class_name>"
        assert self.llm._extract_xml_tag(text, "class_name") == "DataProcessor"

    def test_extracts_multiline_tag(self):
        text = "<rationale>\nThis groups data\nprocessing methods.\n</rationale>"
        result = self.llm._extract_xml_tag(text, "rationale")
        assert result is not None
        assert "data" in result.lower()

    def test_returns_none_for_missing_tag(self):
        text = "<class_name>Foo</class_name>"
        assert self.llm._extract_xml_tag(text, "rationale") is None

    def test_empty_text(self):
        assert self.llm._extract_xml_tag("", "anything") is None


# ── _parse_response ──────────────────────────────────────────────────────────

class TestParseResponse:
    def setup_method(self):
        with patch("genec.core.llm_interface.AnthropicClientWrapper") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.enabled = False
            mock_cls.return_value = mock_instance
            self.llm = LLMInterface(api_key="fake", use_chunking=False, use_hybrid_mode=False)
        self.cluster = _make_cluster()

    def test_valid_response(self):
        response = (
            "<reasoning>These handle coordinate data.</reasoning>\n"
            "<class_name>CoordinateManager</class_name>\n"
            "<rationale>Groups coordinate-related methods.</rationale>\n"
            "<confidence>0.85</confidence>"
        )
        suggestion = self.llm._parse_response(response, self.cluster)
        assert suggestion is not None
        assert suggestion.proposed_class_name == "CoordinateManager"
        assert suggestion.confidence_score == pytest.approx(0.85)
        assert suggestion.reasoning is not None

    def test_missing_class_name_returns_none(self):
        response = "<rationale>Groups methods.</rationale>"
        assert self.llm._parse_response(response, self.cluster) is None

    def test_missing_rationale_returns_none(self):
        response = "<class_name>Foo</class_name>"
        assert self.llm._parse_response(response, self.cluster) is None

    def test_invalid_class_name_returns_none(self):
        response = (
            "<class_name>helper</class_name>\n"
            "<rationale>groups helper methods</rationale>"
        )
        # "helper" starts lowercase -> invalid
        assert self.llm._parse_response(response, self.cluster) is None

    def test_bare_generic_class_name_returns_none(self):
        response = (
            "<class_name>Utils</class_name>\n"
            "<rationale>utility methods</rationale>"
        )
        assert self.llm._parse_response(response, self.cluster) is None

    def test_confidence_clamped(self):
        response = (
            "<class_name>DataStore</class_name>\n"
            "<rationale>stores data</rationale>\n"
            "<confidence>1.5</confidence>"
        )
        suggestion = self.llm._parse_response(response, self.cluster)
        assert suggestion is not None
        assert suggestion.confidence_score == 1.0

    def test_confidence_invalid_string(self):
        response = (
            "<class_name>DataStore</class_name>\n"
            "<rationale>stores data</rationale>\n"
            "<confidence>high</confidence>"
        )
        suggestion = self.llm._parse_response(response, self.cluster)
        assert suggestion is not None
        assert suggestion.confidence_score is None

    def test_empty_response(self):
        assert self.llm._parse_response("", self.cluster) is None

    def test_garbage_response(self):
        assert self.llm._parse_response("random gibberish", self.cluster) is None


# ── _clean_code ──────────────────────────────────────────────────────────────

class TestCleanCode:
    def setup_method(self):
        with patch("genec.core.llm_interface.AnthropicClientWrapper") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.enabled = False
            mock_cls.return_value = mock_instance
            self.llm = LLMInterface(api_key="fake", use_chunking=False, use_hybrid_mode=False)

    def test_strips_markdown_fences(self):
        code = "```java\npublic class Foo {}\n```"
        cleaned = self.llm._clean_code(code)
        assert "```" not in cleaned
        assert "public class Foo {}" in cleaned

    def test_strips_leading_trailing_blank_lines(self):
        code = "\n\n\npublic class Foo {}\n\n\n"
        cleaned = self.llm._clean_code(code)
        assert cleaned == "public class Foo {}"


# ── _extract_method_name_from_signature ──────────────────────────────────────

class TestExtractMethodNameFromSignature:
    def test_simple_signature(self):
        assert LLMInterface._extract_method_name_from_signature("getX()") == "getX"

    def test_with_return_type(self):
        assert LLMInterface._extract_method_name_from_signature("public void foo(int)") == "foo"

    def test_empty(self):
        assert LLMInterface._extract_method_name_from_signature("") is None

    def test_none(self):
        assert LLMInterface._extract_method_name_from_signature(None) is None


# ── Cache behavior ───────────────────────────────────────────────────────────

class TestCacheBehavior:
    def setup_method(self):
        with patch("genec.core.llm_interface.AnthropicClientWrapper") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.enabled = True
            mock_instance.send_message.return_value = (
                "<class_name>CoordinateManager</class_name>\n"
                "<rationale>Groups coordinate methods.</rationale>\n"
                "<confidence>0.9</confidence>"
            )
            mock_cls.return_value = mock_instance
            self.llm = LLMInterface(
                api_key="fake",
                use_chunking=False,
                use_hybrid_mode=False,
                enable_confidence_scoring=False,
            )
            self.mock_llm = mock_instance

    def test_cache_hit_avoids_second_call(self):
        cluster = _make_cluster()
        deps = _make_class_deps()
        code = "public class OriginalClass { private int x; }"

        # First call -> cache miss
        s1 = self.llm.generate_refactoring_suggestion(cluster, code, deps)
        assert s1 is not None
        assert self.llm._cache_misses == 1
        assert self.llm._cache_hits == 0

        # Second call with same cluster -> cache hit
        s2 = self.llm.generate_refactoring_suggestion(cluster, code, deps)
        assert s2 is not None
        assert self.llm._cache_hits == 1
        # The LLM should only have been called once
        assert self.mock_llm.send_message.call_count == 1

    def test_different_clusters_no_cache_hit(self):
        deps = _make_class_deps()
        code = "public class OriginalClass { private int x; }"

        c1 = _make_cluster(cluster_id=0, methods=["foo()"])
        c2 = _make_cluster(cluster_id=1, methods=["bar()"])

        self.llm.generate_refactoring_suggestion(c1, code, deps)
        self.llm.generate_refactoring_suggestion(c2, code, deps)

        assert self.llm._cache_misses == 2
        assert self.llm._cache_hits == 0
        assert self.mock_llm.send_message.call_count == 2


# ── is_available ─────────────────────────────────────────────────────────────

class TestIsAvailable:
    def test_unavailable_without_api_key(self):
        with patch("genec.core.llm_interface.AnthropicClientWrapper") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.enabled = False
            mock_cls.return_value = mock_instance
            llm = LLMInterface(api_key=None, use_chunking=False, use_hybrid_mode=False)
        assert llm.is_available() is False

    def test_available_with_api_key(self):
        with patch("genec.core.llm_interface.AnthropicClientWrapper") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.enabled = True
            mock_cls.return_value = mock_instance
            llm = LLMInterface(api_key="sk-test", use_chunking=False, use_hybrid_mode=False)
        assert llm.is_available() is True


# ── generate returns None when unavailable ───────────────────────────────────

class TestGenerateWhenUnavailable:
    def test_returns_none(self):
        with patch("genec.core.llm_interface.AnthropicClientWrapper") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.enabled = False
            mock_cls.return_value = mock_instance
            llm = LLMInterface(api_key=None, use_chunking=False, use_hybrid_mode=False)

        cluster = _make_cluster()
        deps = _make_class_deps()
        result = llm.generate_refactoring_suggestion(cluster, "code", deps)
        assert result is None

    def test_batch_returns_empty(self):
        with patch("genec.core.llm_interface.AnthropicClientWrapper") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.enabled = False
            mock_cls.return_value = mock_instance
            llm = LLMInterface(api_key=None, use_chunking=False, use_hybrid_mode=False)

        cluster = _make_cluster()
        deps = _make_class_deps()
        results = llm.generate_batch_suggestions([cluster], "code", deps)
        assert results == []
