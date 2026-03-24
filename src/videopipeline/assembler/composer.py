"""FFmpeg video composition engine.

Pipeline:
  1. prepare_scene  — scale/pad each video clip to target resolution, mux with audio
  2. concat         — concatenate segments with xfade / acrossfade transitions
  3. burn_subtitles — hard-sub SRT onto the concatenated video
  4. compose        — orchestrate all three steps into a final output
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from videopipeline.config import Settings
from videopipeline.models.script import VideoScript
from videopipeline.utils.ffmpeg import (
    FFmpegError,
    escape_filter_path,
    get_duration,
    run_ffmpeg,
)
from videopipeline.utils.storage import WorkspaceManager

logger = logging.getLogger(__name__)

# Script transition name  →  FFmpeg xfade transition name (None = hard cut)
XFADE_MAP: dict[str, str | None] = {
    "cut": None,
    "fade": "fade",
    "crossfade": "fadeblack",
    "wipe": "wipeleft",
    "dissolve": "dissolve",
    "slide": "slideleft",
}


class VideoComposer:
    def __init__(self, settings: Settings):
        self.width, self.height = (int(x) for x in settings.output.resolution.split("x"))
        self.fps = settings.output.fps
        self.td = settings.composition.transition_duration
        self.subtitle_font_size = settings.composition.subtitle_font_size
        self.bg_color = settings.composition.background_color

    # ------------------------------------------------------------------ #
    # Step 1 — prepare individual scene segments
    # ------------------------------------------------------------------ #
    def prepare_scene(
        self,
        audio_path: Path,
        output_path: Path,
        video_path: Path | None = None,
    ) -> Path:
        """Merge one video clip + audio into a scene segment at target resolution.

        If *video_path* is ``None`` or missing, a solid-colour background is
        generated whose length matches the audio.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        w, h, fps = self.width, self.height, self.fps

        if video_path and video_path.exists():
            vf = (
                f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
            )
            run_ffmpeg([
                "-i", str(video_path),
                "-i", str(audio_path),
                "-vf", vf,
                "-map", "0:v", "-map", "1:a",
                "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                "-c:a", "aac", "-b:a", "192k",
                "-r", str(fps),
                "-shortest",
                str(output_path),
            ])
        else:
            dur = get_duration(audio_path)
            run_ffmpeg([
                "-f", "lavfi",
                "-i", f"color=c={self.bg_color}:s={w}x{h}:d={dur:.3f}:r={fps}",
                "-i", str(audio_path),
                "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                str(output_path),
            ])

        logger.info("Prepared scene → %s", output_path.name)
        return output_path

    # ------------------------------------------------------------------ #
    # Step 2 — concatenate with transitions
    # ------------------------------------------------------------------ #
    def concat(
        self,
        segments: list[Path],
        transitions: list[str],
        output_path: Path,
    ) -> Path:
        """Concatenate prepared segments.

        *transitions* has ``len(segments) - 1`` entries, one per junction.
        """
        if not segments:
            raise FFmpegError("No segments to concatenate")
        if len(segments) == 1:
            shutil.copy2(segments[0], output_path)
            return output_path

        xfade_types = [XFADE_MAP.get(t, "fade") for t in transitions]

        if all(x is None for x in xfade_types):
            return self._concat_demuxer(segments, output_path)
        return self._concat_xfade(segments, xfade_types, output_path)

    # -- fast stream-copy concat (all cuts, no re-encode) --

    def _concat_demuxer(self, segments: list[Path], output_path: Path) -> Path:
        list_file = output_path.parent / "_concat_list.txt"
        list_file.write_text(
            "\n".join(f"file '{s.as_posix()}'" for s in segments),
            encoding="utf-8",
        )
        run_ffmpeg([
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output_path),
        ])
        list_file.unlink(missing_ok=True)
        logger.info("Concat (demuxer, %d segments) → %s", len(segments), output_path.name)
        return output_path

    # -- xfade / acrossfade concat --

    def _concat_xfade(
        self,
        segments: list[Path],
        xfade_types: list[str | None],
        output_path: Path,
    ) -> Path:
        td = self.td
        durations = [get_duration(s) for s in segments]

        inputs: list[str] = []
        for s in segments:
            inputs.extend(["-i", str(s)])

        v_parts: list[str] = []
        a_parts: list[str] = []

        # Cumulative output duration up to and including current segment
        cum = durations[0]

        for i in range(1, len(segments)):
            trans = xfade_types[i - 1] or "fade"
            offset = max(cum - td, 0)

            # Video labels
            v_in = "[0:v]" if i == 1 else f"[v{i}]"
            v_out = "[vout]" if i == len(segments) - 1 else f"[v{i + 1}]"
            v_parts.append(
                f"{v_in}[{i}:v]xfade=transition={trans}:duration={td}:offset={offset:.3f}{v_out}"
            )

            # Audio labels
            a_in = "[0:a]" if i == 1 else f"[a{i}]"
            a_out = "[aout]" if i == len(segments) - 1 else f"[a{i + 1}]"
            a_parts.append(f"{a_in}[{i}:a]acrossfade=d={td}{a_out}")

            cum += durations[i] - td

        fc = ";".join(v_parts + a_parts)

        run_ffmpeg(
            inputs + [
                "-filter_complex", fc,
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                "-c:a", "aac", "-b:a", "192k",
                str(output_path),
            ]
        )
        logger.info("Concat (xfade, %d segments) → %s", len(segments), output_path.name)
        return output_path

    # ------------------------------------------------------------------ #
    # Step 3 — burn subtitles
    # ------------------------------------------------------------------ #
    def burn_subtitles(
        self,
        video_path: Path,
        subtitle_path: Path,
        output_path: Path,
    ) -> Path:
        """Hard-sub SRT subtitles into *video_path*."""
        sub_escaped = escape_filter_path(subtitle_path)
        style = (
            f"FontSize={self.subtitle_font_size},"
            "PrimaryColour=&Hffffff&,"
            "OutlineColour=&H000000&,"
            "Outline=2"
        )
        run_ffmpeg([
            "-i", str(video_path),
            "-vf", f"subtitles='{sub_escaped}':force_style='{style}'",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "copy",
            str(output_path),
        ])
        logger.info("Subtitles burned → %s", output_path.name)
        return output_path

    # ------------------------------------------------------------------ #
    # Full composition
    # ------------------------------------------------------------------ #
    def compose(
        self,
        script: VideoScript,
        assets: dict[str, list[Path]],
        workspace: WorkspaceManager,
    ) -> Path:
        """Orchestrate the full composition pipeline and return the final video path."""
        audio_map = _build_scene_map(assets.get("audio", []))
        video_map = _build_scene_map(assets.get("video", []))
        subtitle_paths = assets.get("subtitles", [])

        # 1) Prepare each scene
        prepared: list[Path] = []
        transitions: list[str] = []

        for scene in script.scenes:
            if scene.scene_id not in audio_map:
                raise FFmpegError(f"Missing audio for scene {scene.scene_id}")

            out = workspace.prepared_dir / f"scene_{scene.scene_id:03d}.mp4"
            self.prepare_scene(
                audio_path=audio_map[scene.scene_id],
                output_path=out,
                video_path=video_map.get(scene.scene_id),
            )
            prepared.append(out)
            transitions.append(scene.transition)

        # 2) Concatenate — transitions[:-1] covers the junctions between scenes
        concat_out = workspace.base_dir / "_concat.mp4"
        self.concat(prepared, transitions[:-1], concat_out)

        # 3) Burn subtitles → final
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in script.title)
        final_path = workspace.final_video_path(safe_title.strip() or "final")

        if subtitle_paths:
            self.burn_subtitles(concat_out, subtitle_paths[0], final_path)
            concat_out.unlink(missing_ok=True)
        else:
            shutil.move(str(concat_out), str(final_path))

        logger.info("Final video → %s (%.1f MB)", final_path, final_path.stat().st_size / 1e6)
        return final_path


def _build_scene_map(paths: list[Path]) -> dict[int, Path]:
    """``scene_001.mp3`` → ``{1: Path(…)}``"""
    result: dict[int, Path] = {}
    for p in paths:
        try:
            scene_id = int(p.stem.split("_")[1])
            result[scene_id] = p
        except (IndexError, ValueError):
            continue
    return result
