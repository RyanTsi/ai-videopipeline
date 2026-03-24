"""Pipeline orchestration engine — chains generation stages together."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from videopipeline.config import Settings, load_config
from videopipeline.models.script import VideoScript
from videopipeline.utils.storage import WorkspaceManager

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_config()
        self.workspace = WorkspaceManager(Path(self.settings.output.dir))
        self.workspace.setup()

    # ------------------------------------------------------------------
    # Stage 1: Script generation
    # ------------------------------------------------------------------
    def generate_script(self, topic: str, *, language: str | None = None) -> VideoScript:
        from videopipeline.generators.text import TextGenerator

        lang = language or self.settings.pipeline.language
        gen = TextGenerator(self.settings)
        script = gen.generate(topic, language=lang)

        out = self.workspace.scripts_dir / "script.json"
        out.write_text(script.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Script saved → %s", out)
        return script

    # ------------------------------------------------------------------
    # Stage 2: Asset generation (TTS + video clips + subtitles)
    # ------------------------------------------------------------------
    async def generate_assets(self, script: VideoScript) -> dict[str, list[Path]]:
        """Generate TTS audio, video clips, and subtitles concurrently."""
        from videopipeline.generators.audio import create_tts_provider
        from videopipeline.generators.subtitle import SubtitleGenerator
        from videopipeline.generators.video import create_video_provider

        tts = create_tts_provider(self.settings)

        video_gen = None
        try:
            video_gen = create_video_provider(self.settings)
        except (ValueError, ImportError) as exc:
            logger.warning("Video generation unavailable, skipping: %s", exc)

        semaphore = asyncio.Semaphore(self.settings.pipeline.concurrent_tasks)
        audio_paths: list[Path] = []
        video_paths: list[Path] = []

        async def _process_scene(scene):
            async with semaphore:
                audio_out = self.workspace.scene_audio_path(scene.scene_id)
                logger.info("Scene %d: generating TTS …", scene.scene_id)
                await tts.synthesize(scene.narration, audio_out)
                audio_paths.append(audio_out)

                if video_gen:
                    video_out = self.workspace.scene_video_path(scene.scene_id)
                    logger.info("Scene %d: generating video clip …", scene.scene_id)
                    try:
                        await video_gen.generate(
                            scene.visual_prompt, video_out, duration=scene.duration
                        )
                        video_paths.append(video_out)
                    except Exception as exc:
                        logger.warning("Scene %d: video generation failed, skipping: %s", scene.scene_id, exc)

        await asyncio.gather(*[_process_scene(s) for s in script.scenes])

        audio_paths.sort()
        video_paths.sort()

        from videopipeline.utils.ffmpeg import get_duration

        audio_durations: dict[int, float] = {}
        for ap in audio_paths:
            scene_id = int(ap.stem.split("_")[1])
            audio_durations[scene_id] = get_duration(ap)

        sub_gen = SubtitleGenerator()
        sub_path = self.workspace.subtitles_dir / "subtitles.srt"
        sub_gen.save(script, sub_path, audio_durations=audio_durations)

        logger.info(
            "Assets ready: %d audio, %d video clips, 1 subtitle file",
            len(audio_paths),
            len(video_paths),
        )
        return {"audio": audio_paths, "video": video_paths, "subtitles": [sub_path]}

    # ------------------------------------------------------------------
    # Stage 3: Video composition
    # ------------------------------------------------------------------
    def compose_video(self, script: VideoScript, assets: dict[str, list[Path]]) -> Path:
        """Compose final video: prepare scenes → transitions → subtitles."""
        from videopipeline.assembler.composer import VideoComposer
        from videopipeline.utils.ffmpeg import ensure_ffmpeg

        ensure_ffmpeg()
        composer = VideoComposer(self.settings)
        return composer.compose(script, assets, self.workspace)

    # ------------------------------------------------------------------
    # Asset discovery (for running compose independently)
    # ------------------------------------------------------------------
    def discover_assets(self, script: VideoScript) -> dict[str, list[Path]]:
        """Discover existing asset files from the workspace directory."""
        audio = [
            self.workspace.scene_audio_path(s.scene_id)
            for s in script.scenes
            if self.workspace.scene_audio_path(s.scene_id).exists()
        ]
        video = [
            self.workspace.scene_video_path(s.scene_id)
            for s in script.scenes
            if self.workspace.scene_video_path(s.scene_id).exists()
        ]
        sub_path = self.workspace.subtitles_dir / "subtitles.srt"
        subtitles = [sub_path] if sub_path.exists() else []
        return {"audio": audio, "video": video, "subtitles": subtitles}

    # ------------------------------------------------------------------
    # Stage 4: Publish (Phase 4 — stub)
    # ------------------------------------------------------------------
    async def publish(self, video_path: Path, *, platform: str = "youtube") -> str:
        """Publish finished video to a platform. (Phase 4)"""
        raise NotImplementedError("Publishing coming in Phase 4")

    # ------------------------------------------------------------------
    # Full run
    # ------------------------------------------------------------------
    def run(self, topic: str, *, language: str | None = None) -> dict:
        """Execute all implemented pipeline stages.

        Returns dict with 'script', 'assets', and 'video' keys.
        """
        logger.info("Pipeline started — topic: %s", topic)

        script = self.generate_script(topic, language=language)
        assets = asyncio.run(self.generate_assets(script))
        final_video = self.compose_video(script, assets)

        logger.info("Pipeline complete → %s", final_video)
        return {"script": script, "assets": assets, "video": final_video}
