FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TORCH_HOME=/cache/torch

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

# Some YouTube (Music) downloads need Deno for JS signature deciphering, which
# spotDL/yt-dlp shell out to. Pull the static binary from the official image.
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

# Install CUDA-matched torch/torchaudio FIRST from PyTorch's index so a later
# `pip install demucs` can't pull in a CPU-only build and break GPU support.
RUN pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ ./

CMD ["python", "bot.py"]
