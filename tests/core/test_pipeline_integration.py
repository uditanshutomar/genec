"""Integration-style tests for the GenEC pipeline."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from genec.core.pipeline_recorder import PipelineRecorder
from genec.core.stages.base_stage import PipelineContext, PipelineStage
from genec.core.pipeline_runner import PipelineRunner


# ── Helpers ───────────────────────────────────────────────────────────────────

class PassStage(PipelineStage):
    """A stage that always succeeds and sets a result key."""

    def __init__(self, name="pass_stage", result_key=None, result_value=None):
        super().__init__(name)
        self.result_key = result_key
        self.result_value = result_value

    def run(self, context: PipelineContext) -> bool:
        if self.result_key:
            context.results[self.result_key] = self.result_value
        return True


class FailStage(PipelineStage):
    """A stage that always fails."""

    def __init__(self, name="fail_stage"):
        super().__init__(name)

    def run(self, context: PipelineContext) -> bool:
        return False


class ExplodingStage(PipelineStage):
    """A stage that raises an exception."""

    def __init__(self, name="exploding_stage"):
        super().__init__(name)

    def run(self, context: PipelineContext) -> bool:
        raise RuntimeError("Stage exploded")


class TestPipelineRecorderIntegration:
    """Tests for PipelineRecorder attached to PipelineRunner."""

    def test_pipeline_creates_recorder_and_records_stages(self, tmp_path):
        """Pipeline should create a PipelineRecorder and attach to context."""
        context = PipelineContext(
            config={},
            repo_path=str(tmp_path),
            class_file="Foo.java",
        )
        recorder = PipelineRecorder(class_name="Foo")
        context.recorder = recorder

        stages = [
            PassStage("analysis", result_key="all_clusters", result_value=[]),
            PassStage("clustering", result_key="filtered_clusters", result_value=[]),
        ]
        runner = PipelineRunner(stages)
        results = runner.run(context)

        # Verify recorder captured stages
        report = recorder.get_report()
        assert report["class_name"] == "Foo"
        assert "analysis" in report["stages"]
        assert "clustering" in report["stages"]
        assert report["summary"]["stages_completed"] == 2
        assert report["summary"]["total_failures"] == 0

    def test_recorder_report_saves_to_disk(self, tmp_path):
        """Recorder should write a valid JSON report file."""
        recorder = PipelineRecorder(class_name="TestClass")
        recorder.start_stage("analysis")
        recorder.end_stage("analysis", {"method_count": 5})

        report_path = tmp_path / "report.json"
        recorder.save(report_path)

        assert report_path.exists()
        data = json.loads(report_path.read_text())
        assert data["class_name"] == "TestClass"
        assert "analysis" in data["stages"]
        assert data["stages"]["analysis"]["metrics"]["method_count"] == 5

    def test_recorder_captures_failures(self, tmp_path):
        """Recorder should record failures when a stage fails."""
        context = PipelineContext(
            config={},
            repo_path=str(tmp_path),
            class_file="Broken.java",
        )
        recorder = PipelineRecorder(class_name="Broken")
        context.recorder = recorder

        stages = [
            PassStage("setup"),
            FailStage("analysis"),
            PassStage("should_not_run"),
        ]
        runner = PipelineRunner(stages)
        results = runner.run(context)

        report = recorder.get_report()
        assert report["summary"]["total_failures"] == 1
        assert report["summary"]["stages_completed"] == 2  # setup + analysis recorded
        assert results.get("_failed_stage") == "analysis"

    def test_recorder_captures_exceptions(self, tmp_path):
        """Recorder should record exception failures."""
        context = PipelineContext(
            config={},
            repo_path=str(tmp_path),
            class_file="Crash.java",
        )
        recorder = PipelineRecorder(class_name="Crash")
        context.recorder = recorder

        stages = [
            PassStage("setup"),
            ExplodingStage("boom"),
        ]
        runner = PipelineRunner(stages)
        results = runner.run(context)

        report = recorder.get_report()
        assert report["summary"]["total_failures"] == 1
        assert results.get("_failed_stage") == "boom"
        assert "exploded" in results.get("_error", "").lower()


class TestPipelineHandlesNoClusters:
    """Tests for pipeline behavior when no clusters are found."""

    def test_pipeline_handles_no_clusters(self, tmp_path):
        """Pipeline should succeed even if no clusters found."""
        context = PipelineContext(
            config={},
            repo_path=str(tmp_path),
            class_file="SmallClass.java",
        )
        recorder = PipelineRecorder(class_name="SmallClass")
        context.recorder = recorder

        stages = [
            PassStage("analysis", result_key="all_clusters", result_value=[]),
            PassStage("clustering", result_key="filtered_clusters", result_value=[]),
            PassStage("naming", result_key="suggestions", result_value=[]),
        ]
        runner = PipelineRunner(stages)
        results = runner.run(context)

        assert results.get("all_clusters") == []
        assert results.get("filtered_clusters") == []
        assert results.get("suggestions") == []

        report = recorder.get_report()
        assert report["summary"]["total_failures"] == 0
        assert report["summary"]["stages_completed"] == 3

    def test_pipeline_stops_after_failure(self, tmp_path):
        """Stages after a failed stage should not execute."""
        context = PipelineContext(
            config={},
            repo_path=str(tmp_path),
            class_file="Test.java",
        )

        executed = []

        class TrackingStage(PipelineStage):
            def __init__(self, name, should_pass=True):
                super().__init__(name)
                self.should_pass = should_pass

            def run(self, ctx):
                executed.append(self.name)
                return self.should_pass

        stages = [
            TrackingStage("first", should_pass=True),
            TrackingStage("second", should_pass=False),
            TrackingStage("third", should_pass=True),
        ]
        runner = PipelineRunner(stages)
        runner.run(context)

        assert executed == ["first", "second"]
        assert "third" not in executed


class TestPipelineContext:
    """Tests for PipelineContext get/set."""

    def test_get_set_data(self):
        ctx = PipelineContext(config={}, repo_path="/tmp", class_file="A.java")
        ctx.set("key1", 42)
        assert ctx.get("key1") == 42

    def test_get_default(self):
        ctx = PipelineContext(config={}, repo_path="/tmp", class_file="A.java")
        assert ctx.get("nonexistent") is None
        assert ctx.get("nonexistent", "fallback") == "fallback"
