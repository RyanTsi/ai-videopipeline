"""Subtitle generation — produce SRT files from VideoScript timing."""

from __future__ import annotations

import logging
from pathlib import Path

from videopipeline.models.script import VideoScript

logger = logging.getLogger(__name__)


def _format_srt_time(seconds: float) -> str:
    """00:01:23,456"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class SubtitleGenerator:
    """Generate SRT subtitles from a VideoScript.

    If *audio_durations* (scene_id → seconds) is supplied, actual
    audio lengths drive timing.  Otherwise scene.duration is used.
    """

    def generate_srt(
        self,
        script: VideoScript,
        audio_durations: dict[int, float] | None = None,
    ) -> str:
        entries: list[str] = []
        cursor = 0.0

        for scene in script.scenes:
            dur = (
                audio_durations[scene.scene_id]
                if audio_durations and scene.scene_id in audio_durations
                else scene.duration
            )
            start = cursor
            end = cursor + dur

            entries.append(
                f"{len(entries) + 1}\n"
                f"{_format_srt_time(start)} --> {_format_srt_time(end)}\n"
                f"{scene.narration}"
            )
            cursor = end

        return "\n\n".join(entries) + "\n"

    def save(
        self,
        script: VideoScript,
        output_path: Path,
        audio_durations: dict[int, float] | None = None,
    ) -> Path:
        content = self.generate_srt(script, audio_durations)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        logger.info("Subtitles saved → %s", output_path)
        return output_path
