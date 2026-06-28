FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TORCH_HOME=/cache/torch

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

# Install CUDA-matched torch/torchaudio FIRST from PyTorch's index so a later
# `pip install demucs` can't pull in a CPU-only build and break GPU support.
RUN pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY separate.py spotify_dl.py bot.py ./

CMD ["python", "bot.py"]
