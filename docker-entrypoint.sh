#!/bin/sh
# YouTube changes its defenses every few weeks, and a yt-dlp older than that
# fails every download with an opaque HTTP 403. The version baked into the image
# goes stale while the container keeps running, so refresh it on each start:
# `docker compose restart bot` then becomes the fix. Set YTDLP_AUTO_UPDATE=0 to
# skip (e.g. offline).
set -e

if [ "${YTDLP_AUTO_UPDATE:-1}" = "1" ]; then
    echo "Updating yt-dlp..."
    # Non-fatal: without a network we still want the bot to come up.
    PIP_ROOT_USER_ACTION=ignore PIP_DISABLE_PIP_VERSION_CHECK=1 \
        pip install --quiet --no-cache-dir --upgrade yt-dlp \
        || echo "yt-dlp update failed; continuing with the installed version."
    echo "yt-dlp $(yt-dlp --version)"
fi

exec "$@"
