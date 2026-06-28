"""Download a single Spotify track as an mp3 using spotDL."""

import asyncio
import re
from pathlib import Path

# Matches a Spotify track URL, optionally with an /intl-xx/ locale prefix.
TRACK_URL_RE = re.compile(
    r"https?://open\.spotify\.com/(?:intl-[a-z]+/)?track/[A-Za-z0-9]+"
)


class DownloadError(RuntimeError):
    """Raised when spotDL fails to produce an mp3."""


def find_track_url(text: str | None) -> str | None:
    """Return the first Spotify track URL found in ``text``, if any."""
    if not text:
        return None
    match = TRACK_URL_RE.search(text)
    return match.group(0) if match else None


async def download_track(url: str, workdir: str) -> str:
    """Download a Spotify track to ``workdir`` and return the mp3 path."""
    out_dir = Path(workdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    output_template = str(out_dir / "{artists} - {title}.{output-ext}")
    cmd = [
        "spotdl",
        "download",
        url,
        "--output", output_template,
        "--format", "mp3",
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await proc.communicate()
    if proc.returncode != 0:
        raise DownloadError(output.decode(errors="replace"))

    mp3s = sorted(out_dir.glob("*.mp3"))
    if not mp3s:
        raise DownloadError(
            "spotdl finished but produced no mp3.\n" + output.decode(errors="replace")
        )
    return str(mp3s[0])
