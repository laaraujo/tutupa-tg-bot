"""Run Demucs to split an audio file into a target stem vs. everything else."""

import asyncio
import json
from pathlib import Path

# Fine-tuned model: noticeably cleaner separation than plain htdemucs
# (it runs 4 sub-models, so ~4x slower - trivial on a 3090).
MODEL = "htdemucs_ft"

# Which stem to isolate. Demucs two-stem mode produces "<STEM>.flac" and
# "no_<STEM>.flac" (everything else). Options: drums, bass, vocals, other.
STEM = "drums"

# Lossless output so there's no mp3 compression on top of the separation.
FMT = "flac"


class SeparationError(RuntimeError):
    """Raised when the demucs subprocess fails."""


async def separate(input_path: str, workdir: str, device: str = "cuda") -> tuple[str, str]:
    """Split ``input_path`` into two lossless stems using demucs two-stem mode.

    Returns a tuple of ``(stem_path, other_path)`` where ``stem`` is the
    isolated ``STEM`` and ``other`` is the full mix with that stem removed.
    """
    src = Path(input_path)
    out_root = Path(workdir)
    out_root.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python", "-m", "demucs",
        "--two-stems", STEM,
        f"--{FMT}",
        "-n", MODEL,
        "-d", device,
        "-o", str(out_root),
        str(src),
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await proc.communicate()
    if proc.returncode != 0:
        raise SeparationError(output.decode(errors="replace"))

    stem_dir = out_root / MODEL / src.stem
    stem = stem_dir / f"{STEM}.{FMT}"
    other = stem_dir / f"no_{STEM}.{FMT}"
    if not stem.exists() or not other.exists():
        raise SeparationError(
            f"demucs finished but expected outputs are missing in {stem_dir}.\n"
            + output.decode(errors="replace")
        )
    return str(stem), str(other)


async def mix_emphasis(
    stem_path: str,
    other_path: str,
    out_path: str,
    stem_volume: float = 0.7,
    other_volume: float = 0.3,
) -> str:
    """Mix the isolated stem and the rest at the given relative volumes.

    Produces a single lossless file at ``out_path`` where the target stem is at
    ``stem_volume`` and the rest of the mix is at ``other_volume``. Returns
    ``out_path``.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", stem_path,
        "-i", other_path,
        "-filter_complex",
        f"[0:a]volume={stem_volume}[fg];[1:a]volume={other_volume}[bg];"
        "[fg][bg]amix=inputs=2:normalize=0,alimiter=limit=0.97[out]",
        "-map", "[out]",
        "-c:a", "flac",
        out_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await proc.communicate()
    if proc.returncode != 0:
        raise SeparationError(output.decode(errors="replace"))
    return out_path


async def probe_tags(path: str) -> dict:
    """Return the source file's metadata tags (lowercased keys) via ffprobe.

    Returns an empty dict if the file has no tags or ffprobe fails.
    """
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await proc.communicate()
    if proc.returncode != 0:
        return {}
    try:
        data = json.loads(output.decode(errors="replace"))
    except json.JSONDecodeError:
        return {}
    tags = (data.get("format") or {}).get("tags") or {}
    return {str(k).lower(): v for k, v in tags.items()}


async def tag_file(
    src: str,
    dst: str,
    *,
    title: str | None = None,
    artist: str | None = None,
    album: str | None = None,
    comment: str | None = None,
) -> str:
    """Copy ``src`` to ``dst`` (lossless, no re-encode) with metadata tags set."""
    cmd = ["ffmpeg", "-y", "-i", src, "-map", "0:a", "-c", "copy"]
    for key, value in (
        ("title", title),
        ("artist", artist),
        ("album", album),
        ("comment", comment),
    ):
        if value:
            cmd += ["-metadata", f"{key}={value}"]
    cmd.append(dst)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await proc.communicate()
    if proc.returncode != 0:
        raise SeparationError(output.decode(errors="replace"))
    return dst
