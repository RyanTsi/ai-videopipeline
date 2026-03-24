"""Workspace and artifact management — organizes intermediate and final outputs."""

from __future__ import annotations

import shutil
from pathlib import Path


class WorkspaceManager:
    """Manages the directory layout for a single pipeline run."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.scripts_dir = base_dir / "scripts"
        self.audio_dir = base_dir / "audio"
        self.video_clips_dir = base_dir / "video_clips"
        self.subtitles_dir = base_dir / "subtitles"
        self.prepared_dir = base_dir / "prepared"
        self.final_dir = base_dir / "final"

    def setup(self) -> None:
        for d in (
            self.scripts_dir,
            self.audio_dir,
            self.video_clips_dir,
            self.subtitles_dir,
            self.prepared_dir,
            self.final_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    def clean(self) -> None:
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)

    def scene_audio_path(self, scene_id: int) -> Path:
        return self.audio_dir / f"scene_{scene_id:03d}.mp3"

    def scene_video_path(self, scene_id: int) -> Path:
        return self.video_clips_dir / f"scene_{scene_id:03d}.mp4"

    def scene_subtitle_path(self, scene_id: int) -> Path:
        return self.subtitles_dir / f"scene_{scene_id:03d}.srt"

    def final_video_path(self, name: str = "final") -> Path:
        return self.final_dir / f"{name}.mp4"
