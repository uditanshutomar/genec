from genec.core.pipeline_runner import PipelineRunner
from genec.core.stages.base_stage import PipelineContext, PipelineStage
from genec.core.pipeline_recorder import PipelineRecorder


class FakeStage(PipelineStage):
    def __init__(self, name, should_pass=True):
        super().__init__(name)
        self.should_pass = should_pass
    def run(self, context):
        context.results[f"{self.name}_ran"] = True
        return self.should_pass


class TestPipelineRunnerWithRecorder:
    def test_recorder_captures_all_stages(self):
        recorder = PipelineRecorder(class_name="Test")
        ctx = PipelineContext(
            config={}, repo_path="/tmp", class_file="/tmp/Test.java",
            recorder=recorder
        )
        runner = PipelineRunner([FakeStage("a"), FakeStage("b")])
        runner.run(ctx)
        report = recorder.get_report()
        assert "a" in report["stages"]
        assert "b" in report["stages"]

    def test_recorder_stops_on_failure(self):
        recorder = PipelineRecorder(class_name="Test")
        ctx = PipelineContext(
            config={}, repo_path="/tmp", class_file="/tmp/Test.java",
            recorder=recorder
        )
        runner = PipelineRunner([FakeStage("a"), FakeStage("fail", should_pass=False), FakeStage("c")])
        runner.run(ctx)
        report = recorder.get_report()
        assert "a" in report["stages"]
        assert "fail" in report["stages"]
        assert "c" not in report["stages"]
        assert report["summary"]["total_failures"] >= 1

    def test_works_without_recorder(self):
        ctx = PipelineContext(config={}, repo_path="/tmp", class_file="/tmp/Test.java")
        runner = PipelineRunner([FakeStage("a")])
        results = runner.run(ctx)
        assert results["a_ran"] is True
