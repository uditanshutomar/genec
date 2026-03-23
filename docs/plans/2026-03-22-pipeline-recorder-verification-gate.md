# Pipeline Recorder + Hard Verification Gate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add structured per-stage logging (PipelineRecorder), enforce compilation+test gates so only verified suggestions pass, and add unit tests for each pipeline stage.

**Architecture:** PipelineRecorder is injected into PipelineRunner and passed through PipelineContext. Each stage calls recorder.end_stage() with metrics. RefactoringStage enforces a hard gate: suggestions that fail compilation or tests are moved to rejected_suggestions with full diagnostics. Unit tests validate each component independently using existing conftest fixtures.

**Tech Stack:** Python 3.10+, pytest, dataclasses, json, time, existing GenEC infrastructure

---

### Task 1: PipelineRecorder Class

**Files:**
- Create: `genec/core/pipeline_recorder.py`
- Test: `tests/core/test_pipeline_recorder.py`

**Step 1: Write the failing test**

```python
# tests/core/test_pipeline_recorder.py
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
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/uditanshutomar/genec && python -m pytest tests/core/test_pipeline_recorder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'genec.core.pipeline_recorder'`

**Step 3: Write minimal implementation**

```python
# genec/core/pipeline_recorder.py
"""Records per-stage metrics, timing, and diagnostics for the GenEC pipeline."""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class StageRecord:
    """Record for a single pipeline stage."""
    name: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class EventRecord:
    """Record for a pipeline event."""
    name: str
    timestamp: float = 0.0
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class FailureRecord:
    """Record for a pipeline failure."""
    stage: str
    error: str
    timestamp: float = 0.0
    context: dict[str, Any] = field(default_factory=dict)


class PipelineRecorder:
    """Records per-stage metrics, timing, and diagnostics."""

    def __init__(self, class_name: str):
        self.class_name = class_name
        self._stages: dict[str, StageRecord] = {}
        self._events: list[EventRecord] = []
        self._failures: list[FailureRecord] = []
        self._active_stage: str | None = None
        self._pipeline_start = time.monotonic()

    def start_stage(self, name: str) -> None:
        """Mark the beginning of a pipeline stage."""
        record = StageRecord(name=name, start_time=time.monotonic())
        self._stages[name] = record
        self._active_stage = name

    def end_stage(self, name: str, metrics: dict[str, Any]) -> None:
        """Mark the end of a pipeline stage with collected metrics."""
        record = self._stages.get(name)
        if record is None:
            record = StageRecord(name=name, start_time=time.monotonic())
            self._stages[name] = record
        record.end_time = time.monotonic()
        record.duration_ms = (record.end_time - record.start_time) * 1000
        record.metrics = metrics
        self._active_stage = None

    def record_event(self, name: str, data: dict[str, Any]) -> None:
        """Record a notable event during pipeline execution."""
        self._events.append(EventRecord(
            name=name, timestamp=time.monotonic(), data=data
        ))

    def record_failure(self, stage: str, error: str, context: dict[str, Any]) -> None:
        """Record a failure during pipeline execution."""
        self._failures.append(FailureRecord(
            stage=stage, error=error, timestamp=time.monotonic(), context=context
        ))

    def get_report(self) -> dict[str, Any]:
        """Generate the full report as a dictionary."""
        total_ms = (time.monotonic() - self._pipeline_start) * 1000
        return {
            "class_name": self.class_name,
            "total_duration_ms": total_ms,
            "stages": {
                name: {
                    "duration_ms": rec.duration_ms,
                    "metrics": rec.metrics,
                }
                for name, rec in self._stages.items()
            },
            "events": [
                {"name": e.name, "data": e.data}
                for e in self._events
            ],
            "failures": [
                {"stage": f.stage, "error": f.error, "context": f.context}
                for f in self._failures
            ],
            "summary": {
                "total_failures": len(self._failures),
                "total_events": len(self._events),
                "stages_completed": len(self._stages),
            },
        }

    def save(self, output_path: Path) -> None:
        """Write the report as JSON to disk."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(self.get_report(), indent=2, default=str))
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/uditanshutomar/genec && python -m pytest tests/core/test_pipeline_recorder.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add genec/core/pipeline_recorder.py tests/core/test_pipeline_recorder.py
git commit -m "feat: add PipelineRecorder for per-stage metrics and timing"
```

---

### Task 2: Integrate PipelineRecorder into PipelineContext and PipelineRunner

**Files:**
- Modify: `genec/core/stages/base_stage.py` (add recorder to context)
- Modify: `genec/core/pipeline_runner.py` (instrument stage execution)
- Test: `tests/core/test_pipeline_runner.py`

**Step 1: Write the failing test**

```python
# tests/core/test_pipeline_runner.py
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

    def test_works_without_recorder(self):
        ctx = PipelineContext(config={}, repo_path="/tmp", class_file="/tmp/Test.java")
        runner = PipelineRunner([FakeStage("a")])
        results = runner.run(ctx)
        assert results["a_ran"] is True
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/uditanshutomar/genec && python -m pytest tests/core/test_pipeline_runner.py -v`
Expected: FAIL (PipelineContext doesn't accept recorder param yet)

**Step 3: Write minimal implementation**

Modify `genec/core/stages/base_stage.py` — add `recorder` field to PipelineContext:

```python
# Add to PipelineContext dataclass (after results field):
    recorder: "PipelineRecorder | None" = None
```

Modify `genec/core/pipeline_runner.py` — wrap stage execution with recorder calls:

```python
# In PipelineRunner.run(), wrap the stage.run() call:
            recorder = context.recorder
            if recorder:
                recorder.start_stage(stage.name)
            try:
                success = stage.run(context)
                if recorder:
                    recorder.end_stage(stage.name, context.results.get(f"_{stage.name}_metrics", {}))
                if not success:
                    if recorder:
                        recorder.record_failure(stage.name, "Stage returned False", {})
                    # ... existing failure handling
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/uditanshutomar/genec && python -m pytest tests/core/test_pipeline_runner.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add genec/core/stages/base_stage.py genec/core/pipeline_runner.py tests/core/test_pipeline_runner.py
git commit -m "feat: integrate PipelineRecorder into context and runner"
```

---

### Task 3: Add Stage-Level Metric Recording to Each Stage

**Files:**
- Modify: `genec/core/stages/analysis_stage.py`
- Modify: `genec/core/stages/graph_processing_stage.py`
- Modify: `genec/core/stages/clustering_stage.py`
- Modify: `genec/core/stages/naming_stage.py`
- Modify: `genec/core/stages/refactoring_stage.py`

**Step 1: Add timing and metrics to analysis_stage.py**

At the end of `AnalysisStage.run()`, before `return True`:

```python
        # Record metrics
        if context.recorder:
            context.recorder.end_stage("analysis", {
                "methods_found": len(class_deps.methods) if class_deps.methods else 0,
                "fields_found": len(class_deps.fields) if class_deps.fields else 0,
                "method_calls_count": sum(len(v) for v in class_deps.method_calls.values()) if class_deps.method_calls else 0,
                "field_accesses_count": sum(len(v) for v in class_deps.field_accesses.values()) if class_deps.field_accesses else 0,
                "commits_analyzed": getattr(evo_data, 'total_commits', 0),
                "co_changes_found": len(getattr(evo_data, 'co_changes', {})),
                "graph_nodes": G_fused.number_of_nodes() if G_fused else 0,
                "graph_edges": G_fused.number_of_edges() if G_fused else 0,
            })
```

**Step 2: Add to clustering_stage.py**

At the end of `ClusteringStage.run()`, before `return True`:

```python
        if context.recorder:
            context.recorder.end_stage("clustering", {
                "clusters_total": len(all_clusters),
                "clusters_filtered": len(filtered_clusters),
                "clusters_ranked": len(ranked_clusters),
                "clusters_rejected": len(rejected_clusters),
                "avg_cohesion": sum(getattr(c, 'cohesion', 0) for c in ranked_clusters) / max(len(ranked_clusters), 1),
            })
```

**Step 3: Add to naming_stage.py**

At the end of `NamingStage.run()`, before `return True`:

```python
        if context.recorder:
            confidences = [s.confidence_score for s in suggestions if s.confidence_score is not None]
            context.recorder.end_stage("naming", {
                "suggestions_generated": len(suggestions),
                "avg_confidence": sum(confidences) / max(len(confidences), 1),
                "min_confidence": min(confidences) if confidences else 0,
                "max_confidence": max(confidences) if confidences else 0,
            })
```

**Step 4: Add to refactoring_stage.py**

At the end of `RefactoringStage.run()`, before `return True`:

```python
        if context.recorder:
            context.recorder.end_stage("verification", {
                "total_suggestions": len(suggestions),
                "verified_count": len(verified_suggestions),
                "rejected_count": len(suggestions) - len(verified_suggestions),
                "verification_details": [
                    {
                        "name": vr.suggestion_id,
                        "syntactic_pass": vr.syntactic_pass,
                        "semantic_pass": vr.semantic_pass,
                        "behavioral_pass": vr.behavioral_pass,
                        "status": vr.status,
                    }
                    for vr in verification_results
                ],
            })
```

**Step 5: Commit**

```bash
git add genec/core/stages/analysis_stage.py genec/core/stages/graph_processing_stage.py \
        genec/core/stages/clustering_stage.py genec/core/stages/naming_stage.py \
        genec/core/stages/refactoring_stage.py
git commit -m "feat: add per-stage metric recording to all pipeline stages"
```

---

### Task 4: Hard Verification Gate in RefactoringStage

**Files:**
- Modify: `genec/core/stages/refactoring_stage.py`
- Test: `tests/core/test_refactoring_stage.py`

**Step 1: Write the failing test**

```python
# tests/core/test_refactoring_stage.py
from unittest.mock import MagicMock, patch
from genec.core.stages.refactoring_stage import RefactoringStage
from genec.core.stages.base_stage import PipelineContext
from genec.core.pipeline_recorder import PipelineRecorder


def _make_suggestion(name, new_code="class Foo {}", modified_code="class Bar {}", cluster=None):
    s = MagicMock()
    s.proposed_class_name = name
    s.new_class_code = new_code
    s.modified_original_code = modified_code
    s.confidence_score = 0.8
    s.cluster = cluster
    s.verification_status = None
    return s


def _make_verification_result(is_valid, syntactic=True, semantic=True, behavioral=True):
    vr = MagicMock()
    vr.is_valid = is_valid
    vr.syntactic_pass = syntactic
    vr.semantic_pass = semantic
    vr.behavioral_pass = behavioral
    vr.status = "PASS" if is_valid else "FAIL"
    vr.suggestion_id = 0
    vr.error_message = None if is_valid else "compilation failed"
    return vr


class TestHardVerificationGate:
    def test_verified_suggestion_passes_gate(self, tmp_path):
        java_file = tmp_path / "Test.java"
        java_file.write_text("class Test {}")

        engine = MagicMock()
        engine.verify_refactoring.return_value = _make_verification_result(True)

        stage = RefactoringStage(applicator=None, verification_engine=engine)
        ctx = PipelineContext(
            config={"refactoring_application": {"enabled": False}},
            repo_path=str(tmp_path),
            class_file=str(java_file),
        )
        ctx.set("suggestions", [_make_suggestion("GoodHelper")])
        ctx.set("class_deps", MagicMock())
        ctx.results["suggestions"] = ctx.get("suggestions")

        stage.run(ctx)
        assert len(ctx.results["verified_suggestions"]) == 1
        assert ctx.results["verified_suggestions"][0].proposed_class_name == "GoodHelper"

    def test_failed_suggestion_rejected(self, tmp_path):
        java_file = tmp_path / "Test.java"
        java_file.write_text("class Test {}")

        engine = MagicMock()
        engine.verify_refactoring.return_value = _make_verification_result(False)

        stage = RefactoringStage(applicator=None, verification_engine=engine)
        ctx = PipelineContext(
            config={"refactoring_application": {"enabled": False}},
            repo_path=str(tmp_path),
            class_file=str(java_file),
        )
        ctx.set("suggestions", [_make_suggestion("BadHelper")])
        ctx.set("class_deps", MagicMock())
        ctx.results["suggestions"] = ctx.get("suggestions")

        stage.run(ctx)
        assert len(ctx.results["verified_suggestions"]) == 0

    def test_missing_code_skipped(self, tmp_path):
        java_file = tmp_path / "Test.java"
        java_file.write_text("class Test {}")

        engine = MagicMock()
        stage = RefactoringStage(applicator=None, verification_engine=engine)
        ctx = PipelineContext(
            config={"refactoring_application": {"enabled": False}},
            repo_path=str(tmp_path),
            class_file=str(java_file),
        )
        ctx.set("suggestions", [_make_suggestion("NoCode", new_code=None, modified_code=None)])
        ctx.set("class_deps", MagicMock())
        ctx.results["suggestions"] = ctx.get("suggestions")

        stage.run(ctx)
        assert len(ctx.results["verified_suggestions"]) == 0
        engine.verify_refactoring.assert_not_called()

    def test_recorder_captures_verification_metrics(self, tmp_path):
        java_file = tmp_path / "Test.java"
        java_file.write_text("class Test {}")

        engine = MagicMock()
        engine.verify_refactoring.return_value = _make_verification_result(True)

        recorder = PipelineRecorder(class_name="Test")
        stage = RefactoringStage(applicator=None, verification_engine=engine)
        ctx = PipelineContext(
            config={"refactoring_application": {"enabled": False}},
            repo_path=str(tmp_path),
            class_file=str(java_file),
            recorder=recorder,
        )
        ctx.set("suggestions", [_make_suggestion("Helper")])
        ctx.set("class_deps", MagicMock())
        ctx.results["suggestions"] = ctx.get("suggestions")

        stage.run(ctx)
        report = recorder.get_report()
        assert "verification" in report["stages"]
        assert report["stages"]["verification"]["metrics"]["verified_count"] == 1
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/uditanshutomar/genec && python -m pytest tests/core/test_refactoring_stage.py -v`
Expected: Some tests may pass (existing logic already filters), recorder test will fail

**Step 3: Modify refactoring_stage.py**

Add `rejected_suggestions` tracking and recorder integration. After the verification loop, store rejected suggestions:

```python
        # After the for loop, add:
        rejected_suggestions = [s for s in suggestions if s.verification_status not in ("verified",)]
        context.results["rejected_suggestions"] = rejected_suggestions
```

The recorder metrics are added per Task 3 above.

**Step 4: Run test to verify it passes**

Run: `cd /Users/uditanshutomar/genec && python -m pytest tests/core/test_refactoring_stage.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add genec/core/stages/refactoring_stage.py tests/core/test_refactoring_stage.py
git commit -m "feat: enforce hard verification gate, track rejected suggestions"
```

---

### Task 5: Wire PipelineRecorder into Pipeline.run_full_pipeline and Save Report

**Files:**
- Modify: `genec/core/pipeline.py` (lines ~480-510)
- Test: `tests/core/test_pipeline_integration.py`

**Step 1: Write the failing test**

```python
# tests/core/test_pipeline_integration.py
import json
from pathlib import Path
from genec.core.pipeline_recorder import PipelineRecorder


class TestPipelineReportSaving:
    def test_recorder_save_creates_valid_json(self, tmp_path):
        recorder = PipelineRecorder(class_name="IOUtils")
        recorder.start_stage("analysis")
        recorder.end_stage("analysis", {"methods_found": 37})
        recorder.start_stage("clustering")
        recorder.end_stage("clustering", {"clusters_total": 4})
        recorder.record_failure("verification", "javac failed", {"suggestion": "IOHelper"})

        out = tmp_path / "IOUtils_report.json"
        recorder.save(out)

        report = json.loads(out.read_text())
        assert report["class_name"] == "IOUtils"
        assert report["stages"]["analysis"]["metrics"]["methods_found"] == 37
        assert report["stages"]["clustering"]["metrics"]["clusters_total"] == 4
        assert len(report["failures"]) == 1
        assert report["summary"]["stages_completed"] == 2
```

**Step 2: Run test to verify it passes (already implemented)**

Run: `cd /Users/uditanshutomar/genec && python -m pytest tests/core/test_pipeline_integration.py -v`
Expected: PASS

**Step 3: Modify pipeline.py**

In `run_full_pipeline()`, after constructing stages (line ~480) and before `runner = PipelineRunner(stages)`:

```python
        # Create recorder
        recorder = PipelineRecorder(class_name=Path(class_file).stem)
        context.recorder = recorder
```

After `results = runner.run(context)` (line ~495), add:

```python
        # Save pipeline report
        report_dir = Path(repo_path) / ".genec" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        recorder.save(report_dir / f"{Path(class_file).stem}_report.json")
        result.pipeline_report = recorder.get_report()
```

**Step 4: Run existing tests to verify nothing breaks**

Run: `cd /Users/uditanshutomar/genec && python -m pytest tests/ -v --timeout=30`
Expected: All existing tests still PASS

**Step 5: Commit**

```bash
git add genec/core/pipeline.py tests/core/test_pipeline_integration.py
git commit -m "feat: wire PipelineRecorder into pipeline, auto-save reports"
```

---

### Task 6: Unit Tests for Analysis Stage

**Files:**
- Test: `tests/core/test_analysis_stage.py`

**Step 1: Write the tests**

```python
# tests/core/test_analysis_stage.py
from unittest.mock import MagicMock
from genec.core.stages.analysis_stage import AnalysisStage
from genec.core.stages.base_stage import PipelineContext


def _make_class_deps():
    deps = MagicMock()
    deps.methods = [MagicMock(name="m1"), MagicMock(name="m2")]
    deps.fields = [MagicMock(name="f1")]
    deps.method_calls = {"m1()": ["m2()"]}
    deps.field_accesses = {"m1()": ["f1"]}
    deps.get_all_methods.return_value = deps.methods
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
        gb.build_evolutionary_graph.return_value = MagicMock()
        gb.fuse_graphs.return_value = MagicMock(number_of_nodes=lambda: 2, number_of_edges=lambda: 1)

        stage = AnalysisStage(analyzer, evo, gb)
        ctx = PipelineContext(
            config={"evolution": {}, "fusion": {}},
            repo_path="/tmp", class_file="/tmp/Test.java"
        )
        result = stage.run(ctx)
        assert result is True
        assert ctx.get("class_deps") is deps
        assert ctx.get("G_fused") is not None
```

**Step 2: Run tests**

Run: `cd /Users/uditanshutomar/genec && python -m pytest tests/core/test_analysis_stage.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/core/test_analysis_stage.py
git commit -m "test: add unit tests for AnalysisStage"
```

---

### Task 7: Unit Tests for Clustering Stage

**Files:**
- Test: `tests/core/test_clustering_stage.py`

**Step 1: Write the tests**

```python
# tests/core/test_clustering_stage.py
from unittest.mock import MagicMock
from genec.core.stages.clustering_stage import ClusteringStage
from genec.core.stages.base_stage import PipelineContext


class TestClusteringStage:
    def test_returns_false_without_graph(self):
        detector = MagicMock()
        stage = ClusteringStage(detector)
        ctx = PipelineContext(config={}, repo_path="/tmp", class_file="/tmp/T.java")
        # No G_fused or class_deps set
        assert stage.run(ctx) is False

    def test_stores_ranked_clusters(self):
        cluster1 = MagicMock(cohesion=0.8, rejection_issues=None)
        cluster2 = MagicMock(cohesion=0.5, rejection_issues=None)

        detector = MagicMock()
        detector.detect_clusters.return_value = [cluster1, cluster2]
        detector.filter_clusters.return_value = [cluster1, cluster2]
        detector.rank_clusters.return_value = [cluster1, cluster2]

        stage = ClusteringStage(detector)
        ctx = PipelineContext(config={}, repo_path="/tmp", class_file="/tmp/T.java")
        ctx.set("G_fused", MagicMock())
        ctx.set("class_deps", MagicMock())
        ctx.set("evo_data", MagicMock())

        result = stage.run(ctx)
        assert result is True
        assert len(ctx.results["ranked_clusters"]) == 2

    def test_captures_rejected_clusters(self):
        good = MagicMock(cohesion=0.8, rejection_issues=None)
        bad = MagicMock(cohesion=0.1, rejection_issues=["too small"])

        detector = MagicMock()
        detector.detect_clusters.return_value = [good, bad]
        detector.filter_clusters.return_value = [good]
        detector.rank_clusters.return_value = [good]

        stage = ClusteringStage(detector)
        ctx = PipelineContext(config={}, repo_path="/tmp", class_file="/tmp/T.java")
        ctx.set("G_fused", MagicMock())
        ctx.set("class_deps", MagicMock())
        ctx.set("evo_data", MagicMock())

        stage.run(ctx)
        assert len(ctx.results["rejected_clusters"]) == 1
```

**Step 2: Run tests**

Run: `cd /Users/uditanshutomar/genec && python -m pytest tests/core/test_clustering_stage.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/core/test_clustering_stage.py
git commit -m "test: add unit tests for ClusteringStage"
```

---

### Task 8: Unit Tests for Naming Stage

**Files:**
- Test: `tests/core/test_naming_stage.py`

**Step 1: Write the tests**

```python
# tests/core/test_naming_stage.py
import re
from unittest.mock import MagicMock
from genec.core.stages.naming_stage import NamingStage, _auto_name_cluster


class TestAutoNameCluster:
    def test_valid_java_identifier(self):
        cluster = MagicMock()
        cluster.method_signatures = ["getUser()", "setUser(String)", "validateUser()"]
        name = _auto_name_cluster(cluster, "UserService")
        assert re.match(r'^[A-Za-z_$][A-Za-z0-9_$]*$', name), f"Invalid identifier: {name}"

    def test_digit_prefix_sanitized(self):
        cluster = MagicMock()
        cluster.method_signatures = ["123method()"]
        name = _auto_name_cluster(cluster, "MyClass")
        assert not name[0].isdigit(), f"Name starts with digit: {name}"

    def test_fallback_on_empty_methods(self):
        cluster = MagicMock()
        cluster.method_signatures = []
        name = _auto_name_cluster(cluster, "MyClass")
        assert len(name) > 0
        assert re.match(r'^[A-Za-z_$][A-Za-z0-9_$]*$', name)
```

**Step 2: Run tests**

Run: `cd /Users/uditanshutomar/genec && python -m pytest tests/core/test_naming_stage.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/core/test_naming_stage.py
git commit -m "test: add unit tests for NamingStage and auto-naming"
```

---

### Task 9: Unit Tests for Verification Compilation Gate

**Files:**
- Test: `tests/verification/test_compilation_gate.py`

**Step 1: Write the tests**

```python
# tests/verification/test_compilation_gate.py
from unittest.mock import MagicMock, patch
from genec.core.verification_engine import VerificationEngine


class TestCompilationGate:
    def test_valid_code_passes_syntactic(self):
        engine = VerificationEngine(config={
            "enable_syntactic": True,
            "enable_semantic": False,
            "enable_behavioral": False,
        })
        suggestion = MagicMock()
        suggestion.new_class_code = "public class Helper { public void help() {} }"
        suggestion.modified_original_code = "public class Original { }"
        suggestion.proposed_class_name = "Helper"
        suggestion.methods = []
        suggestion.fields = []
        suggestion.cluster = MagicMock(method_signatures=[], field_names=[])

        with patch.object(engine, '_run_syntactic_verification', return_value=(True, [])):
            result = engine.verify_refactoring(
                suggestion=suggestion,
                original_code="public class Original { public void help() {} }",
                original_class_file="/tmp/Original.java",
                repo_path="/tmp",
                class_deps=MagicMock(),
            )
        assert result.syntactic_pass is True

    def test_invalid_code_fails_syntactic(self):
        engine = VerificationEngine(config={
            "enable_syntactic": True,
            "enable_semantic": False,
            "enable_behavioral": False,
        })
        suggestion = MagicMock()
        suggestion.new_class_code = "public class { INVALID"
        suggestion.modified_original_code = "public class Original { }"
        suggestion.proposed_class_name = "Helper"
        suggestion.methods = []
        suggestion.fields = []
        suggestion.cluster = MagicMock(method_signatures=[], field_names=[])

        with patch.object(engine, '_run_syntactic_verification', return_value=(False, ["syntax error"])):
            result = engine.verify_refactoring(
                suggestion=suggestion,
                original_code="public class Original {}",
                original_class_file="/tmp/Original.java",
                repo_path="/tmp",
                class_deps=MagicMock(),
            )
        assert result.syntactic_pass is False
```

**Step 2: Run tests**

Run: `cd /Users/uditanshutomar/genec && python -m pytest tests/verification/test_compilation_gate.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/verification/test_compilation_gate.py
git commit -m "test: add compilation gate tests for VerificationEngine"
```

---

### Task 10: Final Integration — Pipeline Report in CLI Output

**Files:**
- Modify: `genec/cli.py` (add --report-dir flag)
- Modify: `genec/core/pipeline.py` (PipelineResult gets pipeline_report field)

**Step 1: Add pipeline_report field to PipelineResult**

In `genec/core/pipeline.py`, add to the PipelineResult dataclass:

```python
    pipeline_report: dict = field(default_factory=dict)
```

**Step 2: Add --report-dir CLI flag**

In `genec/cli.py`, in the argument parser section:

```python
    parser.add_argument(
        "--report-dir",
        help="Directory to save pipeline reports (default: .genec/reports in repo)",
    )
```

In the main function, after pipeline run, pass report_dir to pipeline if provided.

**Step 3: Run full test suite**

Run: `cd /Users/uditanshutomar/genec && python -m pytest tests/ -v --timeout=30`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add genec/cli.py genec/core/pipeline.py
git commit -m "feat: add --report-dir CLI flag and pipeline_report to PipelineResult"
```

---

## Summary

| Task | What | Files | Tests |
|------|------|-------|-------|
| 1 | PipelineRecorder class | 1 new + 1 test | 6 |
| 2 | Integrate into context/runner | 2 modify + 1 test | 3 |
| 3 | Per-stage metrics in all stages | 5 modify | — |
| 4 | Hard verification gate | 1 modify + 1 test | 4 |
| 5 | Wire into pipeline + save | 1 modify + 1 test | 1 |
| 6 | Analysis stage tests | 1 test | 2 |
| 7 | Clustering stage tests | 1 test | 3 |
| 8 | Naming stage tests | 1 test | 3 |
| 9 | Compilation gate tests | 1 test | 2 |
| 10 | CLI integration | 2 modify | — |
| **Total** | | **15 files** | **24 tests** |
