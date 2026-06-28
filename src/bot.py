"""Telegram bot that splits audio into a target stem vs. everything else.

Send the bot an audio file, or a Spotify track link. It produces an mp3 (via
spotDL for Spotify links), runs Demucs on the GPU, and replies with two tracks:
the isolated stem and the full mix with that stem removed.
"""

import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from separate import FMT, STEM, SeparationError, mix_emphasis, separate
from spotify_dl import DownloadError, download_track, find_track_url
from i18n import resolve_lang, stem_label, t

load_dotenv()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DEVICE = os.environ.get("DEMUCS_DEVICE", "cuda")

# Telegram bots can download files up to 20 MB via the standard Bot API.
MAX_INPUT_BYTES = 20 * 1024 * 1024

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("drumsplit-tg-bot")

# Only one separation at a time so concurrent requests don't fight over the GPU.
job_lock = asyncio.Lock()


def _lang(update: Update) -> str:
    user = update.effective_user
    return resolve_lang(user.language_code if user else None)


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


async def _separate_and_send(
    message, status, input_path: str, workdir: Path, lang: str
) -> None:
    """Run separation on ``input_path`` and reply with the resulting tracks."""
    stem = stem_label(lang, STEM)
    tx = {"stem": stem, "stem_cap": stem.capitalize()}

    if job_lock.locked():
        await status.edit_text(t(lang, "queued"))

    async with job_lock:
        await status.edit_text(t(lang, "separating", **tx))
        stem_path, other_path = await separate(
            input_path, str(workdir / "out"), device=DEVICE
        )
        emphasis_path = str(workdir / f"{STEM}_emphasis.{FMT}")
        await mix_emphasis(
            stem_path, other_path, emphasis_path, stem_volume=1.0, other_volume=0.5
        )

    await status.edit_text(t(lang, "uploading"))
    with open(stem_path, "rb") as fh:
        await message.reply_audio(
            fh, title=t(lang, "title_isolated", **tx), caption=t(lang, "caption_isolated", **tx)
        )
    with open(other_path, "rb") as fh:
        await message.reply_audio(
            fh, title=t(lang, "title_everything", **tx), caption=t(lang, "caption_everything", **tx)
        )
    with open(emphasis_path, "rb") as fh:
        await message.reply_audio(
            fh, title=t(lang, "title_emphasis", **tx), caption=t(lang, "caption_emphasis", **tx)
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

    status = await message.reply_text(t(lang, "downloading"))
    workdir = Path(tempfile.mkdtemp(prefix="drumsplit_"))
    try:
        tg_file = await audio.get_file()
        filename = getattr(audio, "file_name", None) or f"{audio.file_unique_id}.mp3"
        input_path = workdir / filename
        await tg_file.download_to_drive(custom_path=str(input_path))
        await _separate_and_send(message, status, str(input_path), workdir, lang)
    except SeparationError:
        logger.exception("Demucs separation failed")
        await status.edit_text(t(lang, "failed_separation"))
    except Exception as exc:  # noqa: BLE001 - surface unexpected errors to the user
        logger.exception("Unexpected error while handling audio")
        try:
            await status.edit_text(t(lang, "error", error=exc))
        except Exception:
            pass
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    lang = _lang(update)
    url = find_track_url(message.text)
    if url is None:
        await message.reply_text(t(lang, "send_audio_or_link"))
        return

    status = await message.reply_text(t(lang, "fetching_spotify"))
    workdir = Path(tempfile.mkdtemp(prefix="drumsplit_"))
    try:
        input_path = await download_track(url, str(workdir / "dl"))
        await _separate_and_send(message, status, input_path, workdir, lang)
    except DownloadError:
        logger.exception("spotDL download failed")
        await status.edit_text(t(lang, "failed_download"))
    except SeparationError:
        logger.exception("Demucs separation failed")
        await status.edit_text(t(lang, "failed_separation"))
    except Exception as exc:  # noqa: BLE001 - surface unexpected errors to the user
        logger.exception("Unexpected error while handling Spotify link")
        try:
            await status.edit_text(t(lang, "error", error=exc))
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

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(
        MessageHandler(
            filters.AUDIO | filters.VOICE | filters.Document.AUDIO, handle_audio
        )
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )
    logger.info("Bot starting (long polling, device=%s)...", DEVICE)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
