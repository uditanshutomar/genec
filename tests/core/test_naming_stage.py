import re
from unittest.mock import MagicMock
from genec.core.stages.naming_stage import _auto_name_cluster


class TestAutoNameCluster:
    def test_valid_java_identifier(self):
        cluster = MagicMock()
        cluster.get_methods.return_value = ["getUser()", "setUser(String)", "validateUser()"]
        class_deps = MagicMock()
        class_deps.class_name = "UserService"
        name = _auto_name_cluster(cluster, class_deps)
        assert re.match(r'^[A-Za-z_$][A-Za-z0-9_$]*$', name), f"Invalid identifier: {name}"

    def test_digit_prefix_sanitized(self):
        cluster = MagicMock()
        cluster.get_methods.return_value = ["123method()"]
        class_deps = MagicMock()
        class_deps.class_name = "MyClass"
        name = _auto_name_cluster(cluster, class_deps)
        assert not name[0].isdigit(), f"Name starts with digit: {name}"

    def test_fallback_on_empty_methods(self):
        cluster = MagicMock()
        cluster.get_methods.return_value = []
        cluster.id = 1
        class_deps = MagicMock()
        class_deps.class_name = "MyClass"
        name = _auto_name_cluster(cluster, class_deps)
        assert len(name) > 0
        assert re.match(r'^[A-Za-z_$][A-Za-z0-9_$]*$', name)
