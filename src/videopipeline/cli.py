"""Typer CLI — main entry point for the videopipeline tool."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from videopipeline import __version__

app = typer.Typer(
    name="videopipeline",
    help="AI Video Pipeline — from text to video to multi-platform publish.",
    no_args_is_help=True,
)
console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def _load_settings(config: Path | None):
    from videopipeline.config import load_config

    return load_config(config)


def _print_script_table(script) -> None:
    table = Table(title=script.title)
    table.add_column("#", style="dim")
    table.add_column("Duration")
    table.add_column("Narration", max_width=50)
    table.add_column("Transition")
    for s in script.scenes:
        table.add_row(str(s.scene_id), f"{s.duration}s", s.narration[:50], s.transition)
    console.print(table)


# ------------------------------------------------------------------
# generate-script
# ------------------------------------------------------------------
@app.command()
def generate_script(
    topic: str = typer.Argument(..., help="Video topic or outline"),
    output: Path = typer.Option(Path("output/script.json"), "-o", "--output", help="Output path"),
    config: Optional[Path] = typer.Option(None, "-c", "--config", help="YAML config file"),
    language: str = typer.Option("zh", "-l", "--lang", help="Narration language (zh / en)"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
):
    """Generate a structured video script from a topic via LLM."""
    _setup_logging(verbose)
    settings = _load_settings(config)

    from videopipeline.generators.text import TextGenerator

    gen = TextGenerator(settings)
    console.print(f"[bold green]Generating script[/] for: {topic}")

    script = gen.generate(topic, language=language)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(script.model_dump_json(indent=2), encoding="utf-8")

    _print_script_table(script)
    console.print(f"[bold]Script saved → [cyan]{output}[/cyan][/bold]")


# ------------------------------------------------------------------
# generate-video
# ------------------------------------------------------------------
@app.command()
def generate_video(
    script_path: Path = typer.Argument(..., help="Path to script JSON file"),
    config: Optional[Path] = typer.Option(None, "-c", "--config"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
):
    """Generate video assets (TTS audio, video clips, subtitles) from a script."""
    _setup_logging(verbose)
    settings = _load_settings(config)

    from videopipeline.models.script import VideoScript
    from videopipeline.pipeline import Pipeline

    raw = script_path.read_text(encoding="utf-8")
    script = VideoScript.model_validate_json(raw)
    pipe = Pipeline(settings)

    console.print(
        f"[bold green]Generating assets[/] for: {script.title} "
        f"({script.scene_count} scenes, {script.total_duration:.0f}s)"
    )

    assets = asyncio.run(pipe.generate_assets(script))

    console.print(
        f"[bold]Done.[/bold]  Audio: {len(assets['audio'])}, "
        f"Video: {len(assets['video'])}, Subtitles: {len(assets['subtitles'])}"
    )
    for label, paths in assets.items():
        for p in paths:
            console.print(f"  [dim]{label}[/dim] → [cyan]{p}[/cyan]")


# ------------------------------------------------------------------
# compose
# ------------------------------------------------------------------
@app.command()
def compose(
    script_path: Path = typer.Argument(..., help="Path to script JSON file"),
    config: Optional[Path] = typer.Option(None, "-c", "--config"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
):
    """Compose final video from previously generated assets (audio + video clips + subtitles)."""
    _setup_logging(verbose)
    settings = _load_settings(config)

    from videopipeline.models.script import VideoScript
    from videopipeline.pipeline import Pipeline

    raw = script_path.read_text(encoding="utf-8")
    script = VideoScript.model_validate_json(raw)
    pipe = Pipeline(settings)

    assets = pipe.discover_assets(script)
    if not assets["audio"]:
        console.print("[red]No audio assets found. Run generate-video first.[/red]")
        raise typer.Exit(1)

    console.print(
        f"[bold green]Composing video[/] for: {script.title} "
        f"(audio: {len(assets['audio'])}, video: {len(assets['video'])})"
    )

    final = pipe.compose_video(script, assets)
    size_mb = final.stat().st_size / 1e6
    console.print(f"[bold green]Done.[/bold green] Final video → [cyan]{final}[/cyan] ({size_mb:.1f} MB)")


# ------------------------------------------------------------------
# publish  (Phase 4 stub)
# ------------------------------------------------------------------
@app.command()
def publish(
    video: Path = typer.Argument(..., help="Path to final video file"),
    platform: str = typer.Option("youtube", "-p", "--platform", help="Target platform"),
    config: Optional[Path] = typer.Option(None, "-c", "--config"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
):
    """Publish a finished video to a platform. [Phase 4 — not yet implemented]"""
    _setup_logging(verbose)
    console.print("[yellow]Publishing is not yet implemented (Phase 4).[/yellow]")
    raise typer.Exit(1)


# ------------------------------------------------------------------
# run  (full pipeline)
# ------------------------------------------------------------------
@app.command()
def run(
    topic: str = typer.Argument(..., help="Video topic or outline"),
    config: Optional[Path] = typer.Option(None, "-c", "--config"),
    language: str = typer.Option("zh", "-l", "--lang"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
):
    """Run the full pipeline: script → assets → compose → publish.

    Currently executes script generation + asset generation + composition (Phase 1-3).
    """
    _setup_logging(verbose)
    settings = _load_settings(config)

    from videopipeline.pipeline import Pipeline

    pipe = Pipeline(settings)
    console.print(f"[bold green]Running pipeline[/] for: {topic}")

    result = pipe.run(topic, language=language)
    script = result["script"]
    assets = result["assets"]
    final = result["video"]

    _print_script_table(script)
    console.print(
        f"\n[bold]Assets:[/bold]  Audio: {len(assets['audio'])}, "
        f"Video: {len(assets['video'])}, Subtitles: {len(assets['subtitles'])}"
    )
    size_mb = final.stat().st_size / 1e6
    console.print(f"[bold green]Final video → [cyan]{final}[/cyan] ({size_mb:.1f} MB)[/bold green]")


# ------------------------------------------------------------------
# version
# ------------------------------------------------------------------
@app.command()
def version():
    """Print version info."""
    console.print(f"videopipeline [bold]{__version__}[/bold]")
