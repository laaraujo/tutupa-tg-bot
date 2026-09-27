"""Run Demucs to split an audio file into a target stem vs. everything else."""

import asyncio
import json
import math
import re
import struct
import wave
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


def count_in_samples(bpm: float, beats: int, sample_rate: int) -> list[float]:
    """One bar of metronome clicks: an accented tick on beat 1, softer after.

    The buffer is exactly ``beats`` apart, so the song that follows starts on
    the next downbeat. Clicks are synthesized (no spoken count).
    """
    beat_samples = max(1, int(round(sample_rate * 60.0 / bpm)))
    total = beat_samples * beats
    click_len = max(1, int(round(sample_rate * 0.03)))
    samples = [0.0] * total
    for beat in range(beats):
        freq = 1760.0 if beat == 0 else 880.0
        gain = 0.9 if beat == 0 else 0.55
        start = beat * beat_samples
        for n in range(min(click_len, total - start)):
            t = n / sample_rate
            env = math.exp(-t * 90.0)
            tick = math.sin(2 * math.pi * freq * t)
            tick += 0.4 * math.sin(2 * math.pi * freq * 2.5 * t)
            samples[start + n] = gain * env * tick
    peak = max((abs(sample) for sample in samples), default=1.0) or 1.0
    scale = 0.8 / peak
    return [sample * scale for sample in samples]


def _write_count_wav(
    path: Path,
    bpm: float,
    beats: int,
    sample_rate: int,
    channels: int,
) -> None:
    """Write ``count_in_samples`` as 16-bit PCM, duplicated across channels."""
    channels = 1 if channels == 1 else 2
    samples = count_in_samples(bpm, beats, sample_rate)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = bytearray()
        for sample in samples:
            packed = struct.pack("<h", int(max(-1.0, min(1.0, sample)) * 32767))
            frames.extend(packed * channels)
        handle.writeframes(frames)


async def probe_audio(path: str) -> dict:
    """Return ``sample_rate`` and ``channels`` for the first audio stream."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-select_streams", "a:0",
        path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await proc.communicate()
    if proc.returncode != 0:
        raise SeparationError(output.decode(errors="replace"))
    try:
        data = json.loads(output.decode(errors="replace"))
        stream = data["streams"][0]
        return {
            "sample_rate": int(stream["sample_rate"]),
            "channels": int(stream["channels"]),
        }
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SeparationError(f"ffprobe returned no audio stream for {path}") from exc


async def detect_leading_silence(
    path: str,
    noise_db: float = -45.0,
    min_duration: float = 0.03,
) -> float:
    """Return seconds of silence before the first sustained audible signal."""
    cmd = [
        "ffmpeg", "-hide_banner",
        "-i", path,
        "-af", f"silencedetect=noise={noise_db}dB:d={min_duration}",
        "-f", "null", "-",
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await proc.communicate()
    if proc.returncode != 0:
        raise SeparationError(output.decode(errors="replace"))
    text = output.decode(errors="replace")
    # silencedetect emits this only when the file begins below the threshold.
    match = re.search(r"silence_end:\s*([0-9.]+)", text)
    return float(match.group(1)) if match else 0.0


async def prepend_count_in(
    src: str,
    dst: str,
    bpm: float,
    beats: int,
    leading_silence: float = 0.0,
    start_beat: int = 1,
) -> str:
    """Mix one bar of clicks against ``src``, aligned to ``start_beat``.

    ``leading_silence`` is compensated so the source's first audible signal,
    rather than file sample zero, lands on the chosen beat. ``start_beat`` 1
    is the downbeat after the count; 3 or 4 lands on that click of the bar.
    """
    info = await probe_audio(src)
    click_path = Path(dst).with_name(Path(dst).stem + ".count.wav")
    _write_count_wav(
        click_path, bpm, beats, info["sample_rate"], info["channels"]
    )
    layout = "mono" if info["channels"] == 1 else "stereo"
    rate = info["sample_rate"]
    beat_duration = 60.0 / bpm
    # Beat 1 is the downbeat after the whole bar. Any later beat is a pickup
    # on that click, so the remaining clicks overlap the start of the song.
    onset = (
        beats * beat_duration
        if start_beat <= 1
        else (start_beat - 1) * beat_duration
    )
    shift = onset - max(0.0, leading_silence)
    if shift >= 0:
        source_timing = f"adelay={round(shift * rate)}S:all=1"
    else:
        source_timing = f"atrim=start={-shift:.9f},asetpts=PTS-STARTPTS"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(click_path),
        "-i", src,
        "-filter_complex",
        (
            f"[0:a]aformat=sample_fmts=fltp:sample_rates={rate}:"
            f"channel_layouts={layout}[c];"
            f"[1:a]aformat=sample_fmts=fltp:sample_rates={rate}:"
            f"channel_layouts={layout},{source_timing}[s];"
            "[c][s]amix=inputs=2:duration=longest:normalize=0[out]"
        ),
        "-map", "[out]",
        "-c:a", "flac",
        dst,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await proc.communicate()
    if proc.returncode != 0:
        raise SeparationError(output.decode(errors="replace"))
    return dst


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


async def transcode_mp3(
    src: str,
    dst: str,
    *,
    bitrate: str = "320k",
    title: str | None = None,
    artist: str | None = None,
    album: str | None = None,
    comment: str | None = None,
) -> str:
    """Transcode ``src`` to an MP3 at ``bitrate`` with the given metadata tags."""
    cmd = [
        "ffmpeg", "-y",
        "-i", src,
        "-map", "0:a",
        "-c:a", "libmp3lame",
        "-b:a", bitrate,
    ]
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
