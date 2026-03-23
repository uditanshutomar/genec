from genec.core.conceptual_analyzer import _camel_case_split, _extract_method_tokens, build_conceptual_graph
from unittest.mock import MagicMock


class TestCamelCaseSplit:
    def test_simple_camel(self):
        assert _camel_case_split("getUserName") == ["get", "user", "name"]

    def test_all_upper(self):
        # "URL" splits to ["U", "R", "L"], all single chars filtered out
        assert _camel_case_split("URL") == []
        # But "URLParser" should produce tokens
        assert "parser" in _camel_case_split("URLParser")

    def test_underscore(self):
        assert _camel_case_split("get_user") == ["get", "user"]

    def test_single_char_filtered(self):
        # Single-char tokens are filtered out (len > 1)
        result = _camel_case_split("a")
        assert result == []

    def test_pascal_case(self):
        assert _camel_case_split("UserName") == ["user", "name"]


class TestExtractMethodTokens:
    def test_basic_extraction(self):
        m = MagicMock()
        m.name = "getUser"
        m.parameters = []
        m.return_type = "User"
        m.body = ""
        tokens = _extract_method_tokens(m)
        assert "get" in tokens
        assert "user" in tokens

    def test_body_identifiers(self):
        m = MagicMock()
        m.name = "process"
        m.parameters = []
        m.return_type = "void"
        m.body = "this.userName = fetchUserData();"
        tokens = _extract_method_tokens(m)
        assert "user" in tokens
        assert "name" in tokens

    def test_java_keywords_filtered(self):
        m = MagicMock()
        m.name = "check"
        m.parameters = []
        m.return_type = "void"
        m.body = "if (this == null) return;"
        tokens = _extract_method_tokens(m)
        # "if", "this", "null", "return" should not appear
        assert "if" not in tokens.split()
        assert "null" not in tokens.split()


class TestBuildConceptualGraph:
    def test_similar_methods_connected(self):
        m1 = MagicMock(name="getUser", signature="getUser()", body="return this.user;",
                       parameters=[], return_type="User")
        m1.name = "getUser"
        m2 = MagicMock(name="setUser", signature="setUser(User)", body="this.user = user;",
                       parameters=[{"type": "User", "name": "user"}], return_type="void")
        m2.name = "setUser"
        m3 = MagicMock(name="processData", signature="processData()", body="data.transform();",
                       parameters=[], return_type="void")
        m3.name = "processData"

        G = build_conceptual_graph([m1, m2, m3], min_similarity=0.05)
        # getUser and setUser should be more similar to each other than to processData
        assert G.number_of_nodes() >= 3

    def test_empty_methods(self):
        G = build_conceptual_graph([])
        assert G.number_of_nodes() == 0

    def test_single_method(self):
        m = MagicMock(name="foo", signature="foo()", body="", parameters=[], return_type="void")
        m.name = "foo"
        G = build_conceptual_graph([m])
        assert G.number_of_nodes() == 1
        assert G.number_of_edges() == 0

    def test_high_threshold_no_edges(self):
        m1 = MagicMock(name="alpha", signature="alpha()", body="x = 1;",
                       parameters=[], return_type="void")
        m1.name = "alpha"
        m2 = MagicMock(name="beta", signature="beta()", body="y = 2;",
                       parameters=[], return_type="void")
        m2.name = "beta"
        G = build_conceptual_graph([m1, m2], min_similarity=0.99)
        # With very high threshold, dissimilar methods should not connect
        assert G.number_of_edges() == 0

    def test_nodes_use_signature(self):
        m1 = MagicMock(name="foo", signature="foo(int)", body="return x;",
                       parameters=[{"type": "int", "name": "x"}], return_type="int")
        m1.name = "foo"
        m2 = MagicMock(name="bar", signature="bar(int)", body="return y;",
                       parameters=[{"type": "int", "name": "y"}], return_type="int")
        m2.name = "bar"
        G = build_conceptual_graph([m1, m2], min_similarity=0.0)
        assert "foo(int)" in G.nodes()
        assert "bar(int)" in G.nodes()
