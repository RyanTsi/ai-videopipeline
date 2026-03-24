"""Abstract base class for video publishers. (Phase 4)"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class Publisher(ABC):
    @abstractmethod
    async def publish(self, video_path: Path, *, title: str, description: str, tags: list[str]) -> str:
        """Publish a video and return the published URL."""
        ...

    @abstractmethod
    async def check_status(self, publish_id: str) -> str:
        """Check the processing/publish status."""
        ...
