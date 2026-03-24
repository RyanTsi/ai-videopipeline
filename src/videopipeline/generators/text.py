"""LLM-based video script generator — turns a topic into a structured VideoScript."""

from __future__ import annotations

import json
import logging

from openai import OpenAI

from videopipeline.config import Settings
from videopipeline.models.script import VideoScript

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a professional video scriptwriter. Given a topic or outline, \
generate a structured video script in JSON format.

The JSON MUST follow this exact schema:
{
  "title": "Video title",
  "description": "Brief video description",
  "tags": ["tag1", "tag2"],
  "scenes": [
    {
      "scene_id": 1,
      "duration": 5.0,
      "narration": "Narration text for this scene",
      "visual_prompt": "Detailed visual description for AI video generation, cinematic, 4K",
      "transition": "fade"
    }
  ]
}

Rules:
- Generate 3-8 scenes depending on topic complexity.
- Each visual_prompt should be highly detailed, cinematic, suitable for AI video generation.
- Narration should be natural and engaging.
- Transition must be one of: fade, crossfade, cut, wipe.
- Duration: 3-8 seconds per scene.
- Return ONLY valid JSON. No markdown fences, no extra text.\
"""


class TextGenerator:
    def __init__(self, settings: Settings):
        cfg = settings.openai
        if not cfg.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY env var.")
        self.client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
        self.model = cfg.model
        self.max_scenes = settings.pipeline.max_scenes

    def generate(self, topic: str, *, language: str = "zh") -> VideoScript:
        lang_hint = "请用中文撰写旁白。" if language == "zh" else "Write narration in English."
        user_msg = f"Topic: {topic}\n\n{lang_hint}\nMax scenes: {self.max_scenes}"

        logger.info("Calling %s for script generation …", self.model)
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        raw = resp.choices[0].message.content
        if raw is None:
            raise RuntimeError("LLM returned empty response")

        data = json.loads(raw)
        script = VideoScript(**data)
        logger.info(
            "Script generated: %s (%d scenes, %.1fs total)",
            script.title,
            script.scene_count,
            script.total_duration,
        )
        return script
