from types import SimpleNamespace
from unittest.mock import MagicMock
from genec.core.stages.analysis_stage import AnalysisStage
from genec.core.stages.base_stage import PipelineContext


def _make_method(name, signature):
    m = SimpleNamespace(name=name, signature=signature)
    return m


def _make_class_deps():
    m1 = _make_method("m1", "m1()")
    m2 = _make_method("m2", "m2()")
    # Use SimpleNamespace to avoid MagicMock's reserved 'method_calls' attribute
    deps = SimpleNamespace(
        methods=[m1, m2],
        fields=[MagicMock(name="f1")],
        method_calls={"m1()": ["m2()"]},
        field_accesses={"m1()": ["f1"]},
    )
    deps.get_all_methods = lambda: deps.methods
    return deps


class TestAnalysisStage:
    def test_returns_false_on_no_deps(self):
        analyzer = MagicMock()
        analyzer.analyze_class.return_value = None
        evo = MagicMock()
        gb = MagicMock()

        stage = AnalysisStage(analyzer, evo, gb)
        ctx = PipelineContext(config={}, repo_path="/tmp", class_file="/tmp/Test.java")
        assert stage.run(ctx) is False

    def test_stores_class_deps_in_context(self):
        deps = _make_class_deps()
        analyzer = MagicMock()
        analyzer.analyze_class.return_value = deps
        evo = MagicMock()
        evo.mine_method_cochanges.return_value = MagicMock(method_names=[], co_changes={}, total_commits=0)
        gb = MagicMock()
        gb.build_static_graph.return_value = MagicMock()
        evo_graph = MagicMock()
        evo_graph.number_of_edges.return_value = 0
        gb.build_evolutionary_graph.return_value = evo_graph
        fused = MagicMock()
        fused.number_of_nodes.return_value = 2
        fused.number_of_edges.return_value = 1
        gb.fuse_graphs.return_value = fused

        stage = AnalysisStage(analyzer, evo, gb)
        ctx = PipelineContext(
            config={"evolution": {}, "fusion": {}},
            repo_path="/tmp", class_file="/tmp/Test.java"
        )
        result = stage.run(ctx)
        assert result is True
        assert ctx.get("class_deps") is deps
        assert ctx.get("G_fused") is not None
