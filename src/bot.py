"""Telegram bot that splits audio into a target stem vs. everything else.

Send the bot an audio file, or a Spotify track link (downloaded via spotDL).
It asks which output(s) you want, then runs Demucs on the GPU and replies with
the chosen MP3 tracks: the isolated stem, the full mix with that stem removed,
and/or a stem-emphasized mix.
"""

import asyncio
import logging
import os
import re
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from separate import (
    FMT,
    STEM,
    SeparationError,
    mix_emphasis,
    probe_tags,
    separate,
    transcode_mp3,
)
from spotify_dl import DownloadError, download_track, find_track_url
from i18n import resolve_lang, stem_label, t

load_dotenv()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DEVICE = os.environ.get("DEMUCS_DEVICE", "cuda")

# Telegram bots can download files up to 20 MB via the standard Bot API.
MAX_INPUT_BYTES = 20 * 1024 * 1024


def _init_sentry() -> None:
    """Enable Sentry error reporting if SENTRY_DSN is set.

    Uses the default logging integration, which turns every ``logger.exception``
    (and any log at ERROR or above) into a Sentry event, so no other changes
    are needed in the rest of the code.
    """
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return
    import sentry_sdk

    try:
        traces_sample_rate = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0") or 0)
    except ValueError:
        traces_sample_rate = 0.0

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT") or None,
        traces_sample_rate=traces_sample_rate,
        # Telegram messages can contain personal info; keep PII off by default.
        send_default_pii=False,
    )


_init_sentry()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# httpx logs every request at INFO, which floods the logs with the long-polling
# getUpdates calls. Quiet it (and its transport) so only actual usage shows.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("tutupa-tg-bot")

# Only one separation at a time so concurrent requests don't fight over the GPU.
job_lock = asyncio.Lock()

# The selectable outputs, in display order. Each maps to the i18n title key used
# both for the button label and the resulting track title.
OUTPUT_KEYS = ["isolated", "everything", "emphasis"]
OUTPUT_TITLES = {
    "isolated": "title_isolated",
    "everything": "title_everything",
    "emphasis": "title_emphasis",
}

# Pending requests awaiting an output selection, keyed by a short token embedded
# in the inline-keyboard callback data. Telegram limits callback_data to 64
# bytes, so we can't stash the whole request there.
_PENDING_TTL = 3600  # seconds; drop selections the user never confirmed
pending_jobs: dict[str, dict] = {}


def _lang(update: Update) -> str:
    user = update.effective_user
    return resolve_lang(user.language_code if user else None)


def _who(user) -> str:
    """Compact identifier for a Telegram user, for usage logs."""
    if user is None:
        return "unknown"
    username = f"@{user.username}" if user.username else None
    name = user.full_name or None
    parts = [p for p in (username, name) if p]
    return " / ".join(parts) if parts else "?"


def _tx(lang: str) -> dict:
    """Common template kwargs (localized stem name) for message formatting."""
    stem = stem_label(lang, STEM)
    return {"stem": stem, "stem_cap": stem.capitalize()}


def _cleanup_jobs() -> None:
    now = time.monotonic()
    for token in [
        k for k, v in pending_jobs.items() if now - v["created"] > _PENDING_TTL
    ]:
        pending_jobs.pop(token, None)


def _new_job(data: dict) -> str:
    """Register a pending request and return its lookup token."""
    _cleanup_jobs()
    token = uuid.uuid4().hex
    data["created"] = time.monotonic()
    data["selected"] = set()
    pending_jobs[token] = data
    return token


def _build_keyboard(token: str, lang: str, selected: set[str]) -> InlineKeyboardMarkup:
    tx = _tx(lang)
    rows = []
    for index, key in enumerate(OUTPUT_KEYS):
        mark = "\u2705 " if key in selected else "\u2b1c "  # check / empty box
        label = mark + t(lang, OUTPUT_TITLES[key], **tx)
        rows.append(
            [InlineKeyboardButton(label, callback_data=f"s|{token}|t|{index}")]
        )
    rows.append(
        [
            InlineKeyboardButton(
                t(lang, "btn_all"), callback_data=f"s|{token}|all"
            ),
            InlineKeyboardButton(
                t(lang, "btn_send"), callback_data=f"s|{token}|go"
            ),
        ]
    )
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang(update)
    stem = stem_label(lang, STEM)
    await update.message.reply_text(
        t(lang, "help", stem=stem, stem_cap=stem.capitalize())
    )


def _pick_audio(message):
    """Return the audio-bearing attachment from a message, if any."""
    if message.audio:
        return message.audio
    if message.voice:
        return message.voice
    doc = message.document
    if doc and (doc.mime_type or "").startswith("audio"):
        return doc
    return None


def _safe_filename(parts: list[str], ext: str) -> str:
    """Build a filesystem/Telegram-safe filename from non-empty parts."""
    base = " - ".join(p for p in parts if p)
    base = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", base).strip(" .") or "track"
    return f"{base[:120]}.{ext}"


async def _separate_and_send(
    message,
    status,
    input_path: str,
    workdir: Path,
    lang: str,
    selected: set[str],
    meta_hint: dict | None = None,
) -> None:
    """Separate ``input_path`` and reply with the ``selected`` tracks as MP3s."""
    stem = stem_label(lang, STEM)
    tx = {"stem": stem, "stem_cap": stem.capitalize()}

    if job_lock.locked():
        await status.edit_text(t(lang, "queued"))

    async with job_lock:
        await status.edit_text(t(lang, "separating", **tx))
        # demucs two-stem mode produces both stems in one run, so we always
        # separate; only the emphasis mix is extra work we can skip.
        stem_path, other_path = await separate(
            input_path, str(workdir / "out"), device=DEVICE
        )
        emphasis_path = str(workdir / f"{STEM}_emphasis.{FMT}")
        if "emphasis" in selected:
            await mix_emphasis(
                stem_path, other_path, emphasis_path,
                stem_volume=1.0, other_volume=0.5,
            )

    # Source metadata: spotDL embeds full tags; uploads may carry some too.
    tags = await probe_tags(input_path)
    hint = meta_hint or {}
    song = tags.get("title") or hint.get("title") or Path(input_path).stem
    artist = tags.get("artist") or hint.get("artist") or ""
    album = tags.get("album") or ""

    logger.info("separated track: %r by %r (album=%r)", song, artist, album)

    await status.edit_text(t(lang, "uploading"))

    available = {
        "isolated": (stem_path, t(lang, "title_isolated", **tx)),
        "everything": (other_path, t(lang, "title_everything", **tx)),
        "emphasis": (emphasis_path, t(lang, "title_emphasis", **tx)),
    }
    outputs = [available[key] for key in OUTPUT_KEYS if key in selected]
    for index, (path, kind) in enumerate(outputs):
        display_title = f"{song} - {kind}"
        mp3_path = str(workdir / f"out_{index}.mp3")
        await transcode_mp3(
            path, mp3_path,
            title=display_title, artist=artist, album=album, comment=kind,
        )
        filename = _safe_filename([artist, song, kind], "mp3")
        with open(mp3_path, "rb") as fh:
            # Media-sending methods default to a 20s write_timeout that ignores
            # the request-level value set on the Application; separated stems can
            # be several MB, so give the upload the same generous window.
            await message.reply_audio(
                fh,
                title=display_title,
                performer=artist or None,
                filename=filename,
                write_timeout=300,
                read_timeout=300,
                connect_timeout=30,
                pool_timeout=30,
            )
    await status.delete()


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    lang = _lang(update)
    audio = _pick_audio(message)
    if audio is None:
        await message.reply_text(t(lang, "please_send_audio"))
        return

    if audio.file_size and audio.file_size > MAX_INPUT_BYTES:
        await message.reply_text(t(lang, "too_large"))
        return

    logger.info(
        "audio request from %s: file=%r size=%s",
        _who(message.from_user),
        getattr(audio, "file_name", None) or getattr(audio, "title", None),
        audio.file_size,
    )
    token = _new_job(
        {
            "kind": "audio",
            "message": message,
            "audio": audio,
            "meta_hint": {
                "title": getattr(audio, "title", None),
                "artist": getattr(audio, "performer", None),
            },
        }
    )
    await message.reply_text(
        t(lang, "choose_outputs", **_tx(lang)),
        reply_markup=_build_keyboard(token, lang, set()),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    lang = _lang(update)
    url = find_track_url(message.text)
    if url is None:
        await message.reply_text(t(lang, "send_audio_or_link"))
        return

    logger.info("spotify request from %s: url=%s", _who(message.from_user), url)
    token = _new_job({"kind": "spotify", "message": message, "url": url})
    await message.reply_text(
        t(lang, "choose_outputs", **_tx(lang)),
        reply_markup=_build_keyboard(token, lang, set()),
    )


async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline-keyboard taps: toggle outputs or run the confirmed job."""
    query = update.callback_query
    lang = _lang(update)
    parts = query.data.split("|")
    token = parts[1] if len(parts) > 1 else ""
    action = parts[2] if len(parts) > 2 else ""

    job = pending_jobs.get(token)
    if job is None:
        await query.answer()
        await query.edit_message_text(t(lang, "request_expired"))
        return

    if action == "t":
        key = OUTPUT_KEYS[int(parts[3])]
        job["selected"].symmetric_difference_update({key})
        await query.answer()
        await query.edit_message_reply_markup(
            _build_keyboard(token, lang, job["selected"])
        )
        return

    if action == "all":
        job["selected"] = set(OUTPUT_KEYS)
        await query.answer()
        await query.edit_message_reply_markup(
            _build_keyboard(token, lang, job["selected"])
        )
        return

    if action == "go":
        if not job["selected"]:
            await query.answer(t(lang, "select_at_least_one"), show_alert=True)
            return
        pending_jobs.pop(token, None)
        await query.answer()
        await query.edit_message_reply_markup(reply_markup=None)
        await _run_job(job, query.message, lang)


async def _run_job(job: dict, status, lang: str) -> None:
    """Download the source for ``job`` and send the selected separated tracks.

    ``status`` is the keyboard message we reuse as the progress indicator.
    """
    message = job["message"]
    selected = job["selected"]
    source = job["url"] if job["kind"] == "spotify" else "uploaded file"
    logger.info(
        "job start: %s kind=%s outputs=%s source=%s",
        _who(message.from_user),
        job["kind"],
        ",".join(sorted(selected)),
        source,
    )
    started = time.monotonic()
    workdir = Path(tempfile.mkdtemp(prefix="tutupa_"))
    try:
        if job["kind"] == "audio":
            audio = job["audio"]
            await status.edit_text(t(lang, "downloading"))
            tg_file = await audio.get_file()
            filename = (
                getattr(audio, "file_name", None)
                or f"{audio.file_unique_id}.mp3"
            )
            input_path = workdir / filename
            await tg_file.download_to_drive(custom_path=str(input_path))
            await _separate_and_send(
                message, status, str(input_path), workdir, lang, selected,
                job.get("meta_hint"),
            )
        else:
            await status.edit_text(t(lang, "fetching_spotify"))

            async def _searching_alternative() -> None:
                await status.edit_text(t(lang, "searching_alternative"))

            input_path = await download_track(
                job["url"], str(workdir / "dl"),
                on_fallback=_searching_alternative,
            )
            await _separate_and_send(
                message, status, input_path, workdir, lang, selected
            )
        logger.info(
            "job done: %s in %.1fs",
            _who(message.from_user),
            time.monotonic() - started,
        )
    except DownloadError:
        logger.exception("spotDL download failed")
        await status.edit_text(t(lang, "failed_download"))
    except SeparationError:
        logger.exception("Demucs separation failed")
        await status.edit_text(t(lang, "failed_separation"))
    except Exception:  # noqa: BLE001 - surface unexpected errors to the user
        logger.exception("Unexpected error while running job")
        try:
            await status.edit_text(t(lang, "error"))
        except Exception:
            pass
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main() -> None:
    if not TOKEN:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is not set. Create a bot with @BotFather and put "
            "the token in .env (see .env.example)."
        )

    # Audio uploads can be several MB; the default 5s write timeout isn't
    # enough, so give uploads a generous window.
    app = (
        Application.builder()
        .token(TOKEN)
        .connect_timeout(30)
        .read_timeout(300)
        .write_timeout(300)
        .pool_timeout(30)
        .build()
    )
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(
        MessageHandler(
            filters.AUDIO | filters.VOICE | filters.Document.AUDIO, handle_audio
        )
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )
    app.add_handler(CallbackQueryHandler(handle_selection, pattern=r"^s\|"))
    logger.info("Bot starting (long polling, device=%s)...", DEVICE)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
