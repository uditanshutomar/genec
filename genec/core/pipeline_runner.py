import traceback
from typing import Any

from genec.core.stages.base_stage import PipelineContext, PipelineStage
from genec.utils.logging_utils import get_logger


class PipelineRunner:
    """Orchestrator for running pipeline stages."""

    def __init__(self, stages: list[PipelineStage]):
        self.stages = stages
        self.logger = get_logger(self.__class__.__name__)

    def run(self, context: PipelineContext) -> dict[str, Any]:
        """
        Run all stages in the pipeline.

        Args:
            context: Pipeline context

        Returns:
            Dictionary of results from all stages
        """
        self.logger.info(f"Starting pipeline with {len(self.stages)} stages")

        for stage_idx, stage in enumerate(self.stages, 1):
            self.logger.info(f"Running stage {stage_idx}/{len(self.stages)}: {stage.name}")
            recorder = context.recorder
            if recorder:
                recorder.start_stage(stage.name)
            try:
                success = stage.run(context)
                if recorder:
                    stage_metrics = context.results.get(f"_{stage.name}_metrics", {})
                    recorder.end_stage(stage.name, stage_metrics)
                if not success:
                    if recorder:
                        recorder.record_failure(stage.name, "Stage returned False", {})
                    self.logger.error(f"Stage {stage.name} failed (returned False)")
                    context.results["_failed_stage"] = stage.name
                    context.results["_failed_stage_index"] = stage_idx
                    break
            except KeyboardInterrupt:
                self.logger.warning(f"Pipeline cancelled at stage {stage.name}")
                context.results["_failed_stage"] = stage.name
                context.results["_cancelled"] = True
                raise
            except Exception as e:
                if recorder:
                    recorder.record_failure(stage.name, str(e), {})
                self.logger.error(f"Stage {stage.name} failed with exception: {e}")
                self.logger.debug(traceback.format_exc())
                context.results["_failed_stage"] = stage.name
                context.results["_error"] = str(e)
                break

        return context.results
