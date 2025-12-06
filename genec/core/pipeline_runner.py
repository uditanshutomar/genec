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

        for stage in self.stages:
            self.logger.info(f"Running stage: {stage.name}")
            try:
                success = stage.run(context)
                if not success:
                    self.logger.error(f"Stage {stage.name} failed")
                    break
            except Exception as e:
                self.logger.error(f"Stage {stage.name} failed with exception: {e}")
                import traceback

                self.logger.debug(traceback.format_exc())
                break

        return context.results
