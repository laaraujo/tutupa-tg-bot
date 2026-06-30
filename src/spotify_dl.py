"""Download a single Spotify track as an mp3 using spotDL."""

import asyncio
import logging
import re
from pathlib import Path

logger = logging.getLogger("drumsplit-tg-bot")

# Matches a Spotify track URL, optionally with an /intl-xx/ locale prefix.
TRACK_URL_RE = re.compile(
    r"https?://open\.spotify\.com/(?:intl-[a-z]+/)?track/[A-Za-z0-9]+"
)

# YouTube's JS challenge (solved via Deno) occasionally fails on the first try,
# so retry a few times before giving up.
MAX_ATTEMPTS = 3


class DownloadError(RuntimeError):
    """Raised when spotDL fails to produce an mp3."""


def find_track_url(text: str | None) -> str | None:
    """Return the first Spotify track URL found in ``text``, if any."""
    if not text:
        return None
    match = TRACK_URL_RE.search(text)
    return match.group(0) if match else None


async def download_track(url: str, workdir: str) -> str:
    """Download a Spotify track to ``workdir`` and return the mp3 path.

    The YouTube backend is flaky, so this retries a few times before failing.
    """
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

    last_output = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output, _ = await proc.communicate()
        last_output = output.decode(errors="replace")

        mp3s = sorted(out_dir.glob("*.mp3"))
        if proc.returncode == 0 and mp3s:
            return str(mp3s[0])

        logger.warning(
            "spotDL attempt %d/%d failed for %s; retrying",
            attempt, MAX_ATTEMPTS, url,
        )

    raise DownloadError(
        f"spotdl failed after {MAX_ATTEMPTS} attempts.\n" + last_output
    )
