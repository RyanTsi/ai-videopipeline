"""FFmpeg command wrapper — thin abstraction over subprocess calls."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class FFmpegError(RuntimeError):
    """Raised when an FFmpeg command fails."""


def ensure_ffmpeg() -> None:
    """Raise FFmpegError if ffmpeg / ffprobe are not on PATH."""
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise FFmpegError(f"{tool} not found on PATH. Install FFmpeg first.")


def run_ffmpeg(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Execute an ffmpeg command with ``-y`` (overwrite) and raise on failure."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning"] + args
    logger.debug("$ %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise FFmpegError(f"ffmpeg exit {result.returncode}: {result.stderr.strip()}")
    return result


def probe(path: Path) -> dict:
    """Return ffprobe JSON metadata for a media file."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise FFmpegError(f"ffprobe failed on {path}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def get_duration(path: Path) -> float:
    """Get duration of a media file in seconds."""
    info = probe(path)
    return float(info["format"]["duration"])


def escape_filter_path(path: Path) -> str:
    """Escape a file path for use inside an FFmpeg filter expression.

    On Windows ``C:\\Users\\...`` must become ``C\\:/Users/...`` so the
    filter parser does not misinterpret backslashes and colons.
    """
    s = str(path).replace("\\", "/")
    s = s.replace(":", "\\:")
    return s
