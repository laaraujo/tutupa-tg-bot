"""Download a single Spotify track as an mp3 using spotDL.

spotDL matches a Spotify track to a single "best" YouTube source and downloads
only that one. When that source is unusable (e.g. age-restricted, region-locked,
or removed) we fall back to searching YouTube for unrestricted alternates and
try those, while keeping the Spotify metadata via spotDL's ``url|url`` syntax.
"""

import asyncio
import json
import logging
import os
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

logger = logging.getLogger("tutupa-tg-bot")

# Optional Netscape-format cookies file passed to yt-dlp (via spotDL). Used only
# if the file exists; a no-op otherwise.
COOKIE_FILE = os.environ.get("SPOTDL_COOKIE_FILE", "")

# Matches a Spotify track URL, optionally with an /intl-xx/ locale prefix.
TRACK_URL_RE = re.compile(
    r"https?://open\.spotify\.com/(?:intl-[a-z]+/)?track/[A-Za-z0-9]+"
)

# YouTube video IDs are exactly 11 URL-safe characters.
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

# YouTube's JS challenge (solved via Deno) occasionally fails on the first try,
# so retry the primary source a few times before falling back.
MAX_ATTEMPTS = 3

# When the primary source fails, how many search results to consider and how
# many of them to actually attempt downloading.
ALT_SEARCH_RESULTS = 5
ALT_DOWNLOAD_ATTEMPTS = 3


class DownloadError(RuntimeError):
    """Raised when spotDL fails to produce an mp3."""


def find_track_url(text: str | None) -> str | None:
    """Return the first Spotify track URL found in ``text``, if any."""
    if not text:
        return None
    match = TRACK_URL_RE.search(text)
    return match.group(0) if match else None


def _spotdl_download_cmd(spec: str, output_template: str) -> list[str]:
    """Build a spotDL download command. ``spec`` is a Spotify URL, optionally
    ``youtube_url|spotify_url`` to force a specific YouTube source (note the
    order: spotDL requires YouTube first)."""
    cmd = [
        "spotdl",
        "download",
        spec,
        "--output", output_template,
        "--format", "mp3",
    ]
    if COOKIE_FILE and Path(COOKIE_FILE).is_file():
        cmd += ["--cookie-file", COOKIE_FILE]
    return cmd


async def _run(cmd: list[str]) -> tuple[int, str]:
    """Run ``cmd``, returning its exit code and combined stdout/stderr."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await proc.communicate()
    return proc.returncode, output.decode(errors="replace")


def _first_mp3(out_dir: Path) -> str | None:
    mp3s = sorted(out_dir.glob("*.mp3"))
    return str(mp3s[0]) if mp3s else None


async def _track_query(url: str, workdir: Path) -> str | None:
    """Return an "<artist> <title>" search query for a Spotify track, via
    spotDL's metadata dump. Returns None if it can't be determined."""
    save_file = workdir / "track.spotdl"
    await _run(["spotdl", "save", url, "--save-file", str(save_file)])
    if not save_file.is_file():
        return None
    try:
        data = json.loads(save_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    songs = data if isinstance(data, list) else [data]
    if not songs:
        return None
    song = songs[0]
    name = song.get("name") or ""
    artists = song.get("artists") or ([song["artist"]] if song.get("artist") else [])
    artist = artists[0] if artists else ""
    query = f"{artist} {name}".strip()
    return query or None


async def _find_alternatives(url: str, workdir: Path) -> list[str]:
    """Search YouTube for unrestricted (non-age-gated, non-live) alternate
    sources for the track, returning candidate video URLs to try."""
    query = await _track_query(url, workdir)
    if not query:
        logger.warning("Could not determine a search query for %s", url)
        return []

    cmd = [
        "yt-dlp",
        f"ytsearch{ALT_SEARCH_RESULTS}:{query}",
        # Drops age-restricted and live results during extraction.
        "--match-filter", "age_limit<18 & !is_live",
        "--print", "id",  # implies --simulate, so nothing is downloaded here
        "--no-warnings",
        "--ignore-errors",
    ]
    if COOKIE_FILE and Path(COOKIE_FILE).is_file():
        cmd += ["--cookies", COOKIE_FILE]

    _code, out = await _run(cmd)
    ids = [line.strip() for line in out.splitlines() if _VIDEO_ID_RE.match(line.strip())]
    return [f"https://www.youtube.com/watch?v={vid}" for vid in ids[:ALT_DOWNLOAD_ATTEMPTS]]


async def download_track(
    url: str,
    workdir: str,
    on_fallback: Callable[[], Awaitable[None]] | None = None,
) -> str:
    """Download a Spotify track to ``workdir`` and return the mp3 path.

    Tries spotDL's best match first (retried a few times). If that source is
    unusable, searches YouTube for unrestricted alternates and tries those.
    ``on_fallback`` (if given) is awaited once when the fallback search starts,
    so the caller can inform the user.
    """
    out_dir = Path(workdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(out_dir / "{artists} - {title}.{output-ext}")

    # Primary: spotDL's own best match.
    last_output = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        _code, last_output = await _run(_spotdl_download_cmd(url, output_template))
        mp3 = _first_mp3(out_dir)
        if mp3:
            return mp3
        logger.warning(
            "spotDL attempt %d/%d failed for %s; retrying",
            attempt, MAX_ATTEMPTS, url,
        )

    # Fallback: the matched source may be age-restricted/unavailable. Look for
    # unrestricted alternates and try them, keeping the Spotify metadata.
    logger.info("Primary source failed for %s; searching for alternatives", url)
    if on_fallback is not None:
        try:
            await on_fallback()
        except Exception:  # noqa: BLE001 - a status update must never abort the job
            logger.exception("on_fallback callback failed")

    alternatives = await _find_alternatives(url, out_dir)
    for yt_url in alternatives:
        logger.info("Trying alternative source %s", yt_url)
        _code, last_output = await _run(
            _spotdl_download_cmd(f"{yt_url}|{url}", output_template)
        )
        mp3 = _first_mp3(out_dir)
        if mp3:
            return mp3

    raise DownloadError(
        f"spotdl failed after {MAX_ATTEMPTS} attempts"
        + (f" and {len(alternatives)} alternate source(s)" if alternatives else "")
        + ".\n" + last_output
    )
