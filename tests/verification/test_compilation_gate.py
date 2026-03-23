from unittest.mock import MagicMock, patch
from genec.core.verification_engine import VerificationEngine


class TestCompilationGate:
    def test_syntactic_pass_recorded(self):
        engine = VerificationEngine(
            enable_equivalence=False,
            enable_syntactic=True,
            enable_semantic=False,
            enable_behavioral=False,
        )
        suggestion = MagicMock()
        suggestion.new_class_code = "public class Helper { public void help() {} }"
        suggestion.modified_original_code = "public class Original { }"
        suggestion.proposed_class_name = "Helper"
        suggestion.methods = []
        suggestion.fields = []
        suggestion.cluster = MagicMock(method_signatures=[], field_names=[])
        suggestion.cluster_id = 1

        class_deps = MagicMock()
        class_deps.package_name = "com.example"

        with patch.object(engine.syntactic_verifier, 'verify', return_value=(True, None)):
            result = engine.verify_refactoring(
                suggestion=suggestion,
                original_code="public class Original { public void help() {} }",
                original_class_file="/tmp/Original.java",
                repo_path="/tmp",
                class_deps=class_deps,
            )
        assert result.syntactic_pass is True

    def test_syntactic_fail_recorded(self):
        engine = VerificationEngine(
            enable_equivalence=False,
            enable_syntactic=True,
            enable_semantic=False,
            enable_behavioral=False,
        )
        suggestion = MagicMock()
        suggestion.new_class_code = "public class { INVALID"
        suggestion.modified_original_code = "public class Original { }"
        suggestion.proposed_class_name = "Helper"
        suggestion.methods = []
        suggestion.fields = []
        suggestion.cluster = MagicMock(method_signatures=[], field_names=[])
        suggestion.cluster_id = 2

        class_deps = MagicMock()
        class_deps.package_name = "com.example"

        with patch.object(engine.syntactic_verifier, 'verify', return_value=(False, "syntax error")):
            result = engine.verify_refactoring(
                suggestion=suggestion,
                original_code="public class Original {}",
                original_class_file="/tmp/Original.java",
                repo_path="/tmp",
                class_deps=class_deps,
            )
        assert result.syntactic_pass is False
