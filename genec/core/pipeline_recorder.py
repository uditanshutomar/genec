"""Records per-stage metrics, timing, and diagnostics for the GenEC pipeline."""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)


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
            _logger.warning(
                "end_stage('%s') called without matching start_stage(); "
                "creating a fallback record with current time as start",
                name,
            )
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
