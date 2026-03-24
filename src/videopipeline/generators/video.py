"""AI video clip generation — pluggable providers (Runway ML / future backends)."""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from videopipeline.config import Settings

logger = logging.getLogger(__name__)

ASPECT_RATIO_TO_RUNWAY = {
    "16:9": "1280:720",
    "9:16": "720:1280",
    "1:1": "1080:1080",
}

RUNWAY_API_BASE = "https://api.dev.runwayml.com/v1"
RUNWAY_API_VERSION = "2024-11-06"


class VideoProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, output_path: Path, *, duration: float = 5.0) -> Path:
        """Generate a video clip from a text prompt."""
        ...


class RunwayProvider(VideoProvider):
    """Video generation via Runway ML Gen API (raw HTTP, text-to-video)."""

    def __init__(self, settings: Settings, *, prompt_image: str | None = None):
        cfg = settings.video_gen
        if not cfg.api_key:
            raise ValueError("Runway API key required. Set RUNWAYML_API_SECRET env var.")
        self._api_key = cfg.api_key
        self.model = cfg.model
        self.polling_interval = cfg.polling_interval
        self._ratio = ASPECT_RATIO_TO_RUNWAY.get(settings.output.aspect_ratio, "1280:720")
        self._prompt_image = prompt_image

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": RUNWAY_API_VERSION,
        }

    async def generate(self, prompt: str, output_path: Path, *, duration: float = 5.0) -> Path:
        def _sync_generate() -> Path:
            headers = self._headers()

            logger.info(
                "Runway: submitting %s task (%.0fs, %s) …",
                self.model, duration, self._ratio,
            )
            with httpx.Client(timeout=30.0) as client:
                body: dict = {
                    "model": self.model,
                    "promptText": prompt,
                    "ratio": self._ratio,
                    "duration": int(duration),
                }
                if self._prompt_image:
                    body["promptImage"] = self._prompt_image
                    endpoint = f"{RUNWAY_API_BASE}/image_to_video"
                else:
                    endpoint = f"{RUNWAY_API_BASE}/text_to_video"

                resp = client.post(endpoint, headers=headers, json=body)
                if resp.status_code >= 400:
                    logger.error("Runway API error %d: %s", resp.status_code, resp.text)
                    resp.raise_for_status()
                task_id = resp.json()["id"]
                logger.info("Runway: task %s created, polling …", task_id)

                while True:
                    time.sleep(self.polling_interval)
                    status_resp = client.get(
                        f"{RUNWAY_API_BASE}/tasks/{task_id}",
                        headers=headers,
                    )
                    status_resp.raise_for_status()
                    task = status_resp.json()
                    status = task.get("status", "UNKNOWN")
                    logger.debug("Runway: task %s → %s", task_id, status)

                    if status == "SUCCEEDED":
                        video_url = task["output"][0]
                        break
                    if status in ("FAILED", "CANCELLED"):
                        raise RuntimeError(
                            f"Runway task {task_id} {status}: "
                            f"{task.get('failure', task.get('failureCode', 'unknown'))}"
                        )

                logger.info("Runway: downloading result …")
                dl = client.get(video_url, follow_redirects=True, timeout=120.0)
                dl.raise_for_status()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(dl.content)

            return output_path

        return await asyncio.to_thread(_sync_generate)


def create_video_provider(settings: Settings) -> VideoProvider:
    """Factory — instantiate the configured video provider."""
    provider = settings.video_gen.provider.lower()
    if provider == "runway":
        return RunwayProvider(settings)
    raise ValueError(f"Unknown video provider: {settings.video_gen.provider!r}")
