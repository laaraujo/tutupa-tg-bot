# lausplitter backend

A Telegram bot that splits an audio file into two tracks using
[Demucs](https://github.com/facebookresearch/demucs):

- **drums** (percussion)
- **everything else** (the mix with drums removed)

It runs entirely on your machine. Demucs uses the GPU (RTX 3090) inside a Docker
container. Because the bot talks to Telegram via outbound long-polling, there is
no inbound networking to configure (no port forwarding, no tunnels).

## How it works

```
phone (Telegram) -> Telegram servers <- bot (GPU container) -> Demucs (GPU)
```

You send the bot an audio file **or a Spotify track link**; it produces an mp3
(via [spotDL](https://github.com/spotDL/spotify-downloader) for Spotify links,
which sources the audio from YouTube Music), runs `demucs --two-stems` on the
GPU, and sends both resulting tracks back.

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
the Demucs model weights (~80 MB) into `./cache`, so later runs are fast.

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

## Verify the GPU is visible to the container

```bash
docker compose run --rm bot python -c "import torch; print(torch.cuda.is_available())"
```

This should print `True`.
