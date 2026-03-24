from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class OpenAIConfig(BaseModel):
    api_key: str = ""
    model: str = "gpt-4o"
    base_url: str | None = None


class TTSConfig(BaseModel):
    provider: str = "openai"
    voice: str = "alloy"
    model: str = "tts-1"
    edge_voice: str = "zh-CN-XiaoxiaoNeural"


class VideoGenConfig(BaseModel):
    provider: str = "runway"
    api_key: str = ""
    model: str = "gen4.5"
    polling_interval: int = 10


class OutputConfig(BaseModel):
    dir: Path = Path("output")
    resolution: str = "1920x1080"
    fps: int = 30
    aspect_ratio: str = "16:9"


class PipelineConfig(BaseModel):
    language: str = "zh"
    max_scenes: int = 8
    concurrent_tasks: int = 3


class CompositionConfig(BaseModel):
    transition_duration: float = 0.5
    subtitle_font_size: int = 24
    background_color: str = "black"


class Settings(BaseModel):
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    video_gen: VideoGenConfig = Field(default_factory=VideoGenConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    composition: CompositionConfig = Field(default_factory=CompositionConfig)


def _apply_env_overrides(settings: Settings) -> None:
    """Override settings with environment variables where applicable."""
    if key := os.environ.get("OPENAI_API_KEY"):
        settings.openai.api_key = key
    if url := os.environ.get("OPENAI_BASE_URL"):
        settings.openai.base_url = url
    if model := os.environ.get("OPENAI_MODEL"):
        settings.openai.model = model
    if key := os.environ.get("RUNWAYML_API_SECRET"):
        settings.video_gen.api_key = key


def load_config(config_path: Path | None = None) -> Settings:
    """Load .env → YAML → env-var overrides, in that order."""
    from dotenv import load_dotenv

    load_dotenv()

    data: dict = {}
    path = config_path or Path("config/default.yaml")
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    settings = Settings(**data)
    _apply_env_overrides(settings)
    return settings
