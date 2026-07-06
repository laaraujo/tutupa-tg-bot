# tutupa-tg-bot

A Telegram bot that splits audio into stems using the fine-tuned
[Demucs](https://github.com/facebookresearch/demucs) model (`htdemucs_ft`). Send
it a track and it lets you pick which of these outputs you want (any
combination), then returns each as a 320 kbps MP3:

- **Just drums** (the isolated percussion)
- **No drums** (the mix with drums removed)
- **drums emphasized** (drums at 100%, everything else at 50%)

Messages are localized in English and Spanish based on your Telegram language.

It runs entirely on your machine. Demucs uses the GPU (RTX 3090) inside a Docker
container. Because the bot talks to Telegram via outbound long-polling, there is
no inbound networking to configure (no port forwarding, no tunnels).

## Project layout

```
.                     # Docker + config live at the root
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env              # your bot token (not committed)
├── cache/            # Demucs model weights (persisted)
├── botmeta/          # version-controlled bot profile texts + apply script
└── src/              # all Python code
    ├── bot.py        # Telegram bot
    ├── separate.py   # Demucs + ffmpeg mixing
    ├── spotify_dl.py # Spotify link -> mp3 via spotDL
    └── i18n.py       # user-facing strings (en/es)
```

## How it works

```
phone (Telegram) -> Telegram servers <- bot (GPU container) -> Demucs (GPU)
```

You send the bot an audio file **or a Spotify track link**; it produces an mp3
(via [spotDL](https://github.com/spotDL/spotify-downloader) for Spotify links,
which sources the audio from YouTube Music). The bot then shows an inline
keyboard so you can choose which output(s) you want; once you confirm, it runs
`demucs --two-stems` on the GPU and sends back each selected track as an MP3.

> Note: downloading from Spotify via third-party tooling is against Spotify's
> Terms of Service. Use this for personal purposes only.

## One-time setup

1. Create a bot and get its token:
   - In Telegram, message [@BotFather](https://t.me/BotFather), send `/newbot`,
     follow the prompts, and copy the token it gives you.
2. Create your `.env`:
   ```bash
   cp .env.example .env
   # then edit .env and paste your token after TELEGRAM_BOT_TOKEN=
   ```

## Run

```bash
docker compose up --build
```

The first build downloads CUDA PyTorch (large); the first separation downloads
the fine-tuned Demucs model weights (~320 MB) into `./cache`, so later runs are
fast.

Then open Telegram, find your bot, and send it an audio file. Send `/start` for
usage help.

To run it in the background:

```bash
docker compose up --build -d
docker compose logs -f      # follow logs
docker compose down         # stop
```

## Notes / limits

- **File size:** Telegram's Bot API limits bot downloads to ~20 MB and uploads
  to ~50 MB per file. Typical songs fit; for larger files you'd need a
  self-hosted Telegram Bot API server (not set up here).
- **GPU vs CPU:** set `DEMUCS_DEVICE=cpu` in `.env` to run without the GPU
  (much slower).
- **One at a time:** the bot processes a single track at a time and queues the
  rest, so concurrent requests don't fight over the GPU.

## Bot profile texts (descriptions)

The bot's localized profile texts live in `botmeta/` so they're version
controlled:

- `description.<lang>.txt` -> the empty-chat description (`setMyDescription`)
- `short_description.<lang>.txt` -> the contact-card "about" (`setMyShortDescription`)

`en` is sent as the default (fallback for every locale); any other language code
(e.g. `es`) is applied to that specific locale. To push changes to Telegram:

```bash
./botmeta/apply.sh
```

It reads `TELEGRAM_BOT_TOKEN` from `.env`.

## Verify the GPU is visible to the container

```bash
docker compose run --rm bot python -c "import torch; print(torch.cuda.is_available())"
```

This should print `True`.
