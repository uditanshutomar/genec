# Design: Pipeline Recorder + Hard Verification Gate + Per-Stage Tests

**Date:** 2026-03-22
**Goal:** Instrument every pipeline stage with structured logging, enforce compilation + test-passing gates on all suggestions, and add unit tests for each stage.

---

## 1. PipelineRecorder

New class `genec/core/pipeline_recorder.py` that instruments the pipeline.

### API

```python
class PipelineRecorder:
    def start_stage(self, name: str) -> None
    def end_stage(self, name: str, metrics: dict) -> None
    def record_event(self, name: str, data: dict) -> None
    def record_failure(self, name: str, error: str, context: dict) -> None
    def save(self, output_path: Path) -> None  # writes JSON report
```

### Metrics per stage

| Stage | Metrics |
|-------|---------|
| Analysis | methods_found, fields_found, method_calls_count, field_accesses_count, parse_time_ms |
| Evolutionary | commits_analyzed, co_changes_found, window_months, evo_time_ms |
| Graph | nodes, edges, avg_edge_weight, alpha_used, fusion_time_ms |
| Clustering | clusters_total, clusters_filtered, clusters_by_tier, avg_cohesion, cluster_time_ms |
| Naming | suggestions_generated, llm_tokens_used, avg_confidence, naming_time_ms |
| Verification | per_suggestion: {compiled, tests_passed, tests_run, syntactic_errors, semantic_errors} |

### Output

One `{class_name}_report.json` per run containing all stage data + final suggestions.

---

## 2. Hard Verification Gate

### Current flow
```
suggestion -> verify -> tag pass/fail -> include all in output
```

### New flow
```
suggestion -> compile (javac) -> fail? drop + record reason
           -> run tests      -> fail? drop + record reason
           -> pass?           -> include as "verified"
```

### Changes
- `VerificationEngine.verify()` returns `VerificationVerdict` (PASS/FAIL/SKIP + reason)
- `RefactoringStage` filters: only PASS suggestions in `context["suggestions"]`
- Failed go to `context["rejected_suggestions"]` with diagnostics
- Recorder captures both verified and rejected

### Compilation check
- `javac` on new extracted class AND modified original
- Stub generation for missing deps (existing syntactic_verifier)
- Optional full Maven/Gradle build

### Behavioral check
- Discover tests referencing original class (existing test_finder)
- Run tests against refactored code
- Compare: same pass/fail = behavioral equivalence
- Restore originals after (existing backup/restore)

---

## 3. Per-Stage Unit Tests

| Test File | Tests |
|-----------|-------|
| tests/core/test_pipeline_recorder.py | Timing, metrics, JSON output |
| tests/core/test_analysis_stage.py | Valid ClassDependencies from sample Java |
| tests/core/test_clustering_stage.py | Min/max size, quality scoring |
| tests/core/test_naming_stage.py | Valid Java identifiers, LLM mock |
| tests/core/test_refactoring_stage.py | Gate drops failed, keeps passed |
| tests/verification/test_compilation_gate.py | Valid compiles, invalid rejected, stubs |
| tests/verification/test_behavioral_gate.py | Test preservation, backup/restore |

Uses existing conftest.py fixtures.

---

## 4. Integration

```
CLI -> pipeline.run_full_pipeline()
  recorder = PipelineRecorder()
  Stage 1: Analysis     -> recorder.end_stage(...)
  Stage 2: Graph        -> recorder.end_stage(...)
  Stage 3: Clustering   -> recorder.end_stage(...)
  Stage 4: Naming       -> recorder.end_stage(...)
  Stage 5: Refactoring  -> HARD GATE
    For each suggestion:
      compile -> fail? rejected + recorder.record_failure()
      tests   -> fail? rejected + recorder.record_failure()
      pass?   -> verified_suggestions
    recorder.end_stage("verification", {passed: N, failed: M})
  recorder.save("results/{class_name}_report.json")
```

- CLI stdout JSON: only verified suggestions
- Report file: everything (verified + rejected + all metrics)
- Evaluation scripts read reports for paper tables
