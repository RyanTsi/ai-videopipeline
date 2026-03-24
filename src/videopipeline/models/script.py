"""Data models for the structured video script — the core contract between all pipeline stages."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Scene(BaseModel):
    scene_id: int
    duration: float = 5.0
    narration: str
    visual_prompt: str
    transition: str = "fade"


class VideoScript(BaseModel):
    title: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    scenes: list[Scene]

    @property
    def total_duration(self) -> float:
        return sum(s.duration for s in self.scenes)

    @property
    def scene_count(self) -> int:
        return len(self.scenes)
