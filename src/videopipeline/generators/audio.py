"""TTS audio synthesis — pluggable providers (OpenAI TTS / edge-tts)."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from videopipeline.config import Settings

logger = logging.getLogger(__name__)


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, output_path: Path) -> Path:
        """Convert text to speech and write to output_path."""
        ...


class OpenAITTSProvider(TTSProvider):
    """TTS via OpenAI Audio API (tts-1 / tts-1-hd)."""

    def __init__(self, settings: Settings):
        from openai import OpenAI

        cfg = settings.openai
        if not cfg.api_key:
            raise ValueError("OpenAI API key is required for TTS. Set OPENAI_API_KEY env var.")
        self.client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
        self.model = settings.tts.model
        self.voice = settings.tts.voice

    async def synthesize(self, text: str, output_path: Path) -> Path:
        def _call():
            resp = self.client.audio.speech.create(model=self.model, voice=self.voice, input=text)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            resp.stream_to_file(str(output_path))
            return output_path

        return await asyncio.to_thread(_call)


class EdgeTTSProvider(TTSProvider):
    """TTS via edge-tts (free, Microsoft Edge online TTS)."""

    def __init__(self, settings: Settings):
        self.voice = settings.tts.edge_voice

    async def synthesize(self, text: str, output_path: Path) -> Path:
        try:
            import edge_tts
        except ImportError as exc:
            raise ImportError(
                "edge-tts is not installed. Run: pip install 'ai-videopipeline[tts]'"
            ) from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(str(output_path))
        logger.debug("edge-tts saved → %s", output_path)
        return output_path


def create_tts_provider(settings: Settings) -> TTSProvider:
    """Factory — instantiate the configured TTS provider."""
    provider = settings.tts.provider.lower().replace("-", "")
    if provider == "openai":
        return OpenAITTSProvider(settings)
    if provider in ("edgetts", "edge_tts"):
        return EdgeTTSProvider(settings)
    raise ValueError(f"Unknown TTS provider: {settings.tts.provider!r}")
