import json
import time
from pathlib import Path
from genec.core.pipeline_recorder import PipelineRecorder


class TestPipelineRecorder:
    def test_start_and_end_stage(self):
        recorder = PipelineRecorder(class_name="TestClass")
        recorder.start_stage("analysis")
        time.sleep(0.01)
        recorder.end_stage("analysis", {"methods_found": 10, "fields_found": 3})
        report = recorder.get_report()
        assert "analysis" in report["stages"]
        stage = report["stages"]["analysis"]
        assert stage["metrics"]["methods_found"] == 10
        assert stage["duration_ms"] >= 10

    def test_record_event(self):
        recorder = PipelineRecorder(class_name="TestClass")
        recorder.record_event("cluster_found", {"size": 5, "cohesion": 0.8})
        report = recorder.get_report()
        assert len(report["events"]) == 1
        assert report["events"][0]["name"] == "cluster_found"

    def test_record_failure(self):
        recorder = PipelineRecorder(class_name="TestClass")
        recorder.record_failure("verification", "compilation failed", {"suggestion": "FooHelper"})
        report = recorder.get_report()
        assert len(report["failures"]) == 1
        assert report["failures"][0]["stage"] == "verification"

    def test_save_json(self, tmp_path):
        recorder = PipelineRecorder(class_name="TestClass")
        recorder.start_stage("analysis")
        recorder.end_stage("analysis", {"methods_found": 5})
        out = tmp_path / "report.json"
        recorder.save(out)
        loaded = json.loads(out.read_text())
        assert loaded["class_name"] == "TestClass"
        assert "analysis" in loaded["stages"]

    def test_total_duration(self):
        recorder = PipelineRecorder(class_name="TestClass")
        recorder.start_stage("a")
        recorder.end_stage("a", {})
        recorder.start_stage("b")
        recorder.end_stage("b", {})
        report = recorder.get_report()
        assert report["total_duration_ms"] >= 0

    def test_summary_counts(self):
        recorder = PipelineRecorder(class_name="TestClass")
        recorder.record_failure("v", "err1", {})
        recorder.record_failure("v", "err2", {})
        recorder.record_event("ok", {})
        report = recorder.get_report()
        assert report["summary"]["total_failures"] == 2
        assert report["summary"]["total_events"] == 1
