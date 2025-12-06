"""Base classes for pipeline stages."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from genec.utils.logging_utils import get_logger


@dataclass
class PipelineContext:
    """Shared context for pipeline stages."""

    config: dict[str, Any]
    repo_path: str
    class_file: str
    data: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get data from context."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        """Set data in context."""
        self.data[key] = value


class PipelineStage(ABC):
    """Abstract base class for pipeline stages."""

    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    def run(self, context: PipelineContext) -> bool:
        """
        Run the stage.

        Args:
            context: Shared pipeline context

        Returns:
            True if successful, False otherwise
        """
        pass
