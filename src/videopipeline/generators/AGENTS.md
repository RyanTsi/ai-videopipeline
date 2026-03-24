# generators/

Content generation modules. Each generator takes configuration + input and produces artifacts.

- `text.py` — LLM-based script generation (OpenAI GPT). **Implemented.**
- `audio.py` — TTS synthesis: `OpenAITTSProvider` + `EdgeTTSProvider`. Factory: `create_tts_provider()`. **Implemented.**
- `video.py` — AI video clip generation: `RunwayProvider`. Factory: `create_video_provider()`. **Implemented.**
- `subtitle.py` — SRT subtitle generation from `VideoScript` timing. **Implemented.**

## Convention

- New providers implement the abstract base class (`TTSProvider` / `VideoProvider`) and are selected via config `provider` field.
- All generators receive a `Settings` object; they must NOT read env vars directly.
- Async methods use `asyncio.to_thread()` to wrap synchronous SDK calls.
