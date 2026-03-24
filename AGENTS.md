# AI Video Pipeline — Root

## What this project does

AI-driven video production pipeline: text → structured script → asset generation → video composition → multi-platform publishing.

## Directory layout

```
ai-videopipeline/
├── src/videopipeline/        # Main Python package (src-layout)
│   ├── cli.py                # Typer CLI entry point
│   ├── config.py             # YAML + Pydantic configuration
│   ├── pipeline.py           # Orchestration engine
│   ├── models/               # Data models (VideoScript, Scene)
│   ├── generators/           # Content generators (text, audio, video, subtitle)
│   ├── assembler/            # FFmpeg video composition
│   ├── publishers/           # Platform publishers (YouTube, Bilibili)
│   └── utils/                # Shared utilities (storage, ffmpeg wrapper)
├── config/                   # YAML configuration templates
├── output/                   # Generated artifacts (gitignored)
├── tests/                    # Test suite
└── pyproject.toml            # Build & dependency config
```

## Conventions

- **Language**: Python 3.11+, type hints everywhere, `from __future__ import annotations`.
- **Config**: YAML file at `config/default.yaml`, secrets via env vars (never committed).
- **Data contract**: All stages communicate via `VideoScript` model (see `models/script.py`).
- **Pluggable backends**: generators and publishers use abstract base classes; add new providers by implementing the interface.
- **CLI**: All user-facing commands go through `cli.py` (Typer).

## Implementation status

- **Phase 1** (current): project skeleton, config, script generation, CLI
- **Phase 2**: TTS, AI video generation, subtitles
- **Phase 3**: FFmpeg composition
- **Phase 4**: multi-platform publishing
- **Phase 5**: batch tasks, resume, GUI
