#!/usr/bin/env bash
# Push the bot's localized profile texts to Telegram via the Bot API.
#
# Reads TELEGRAM_BOT_TOKEN from ../.env. Run from anywhere:
#   ./botmeta/apply.sh
#
# Sources, relative to this folder:
#   description.<lang>.txt        -> setMyDescription (empty-chat description)
#   short_description.<lang>.txt  -> setMyShortDescription (contact-card "about")
# The "en" file is sent as the default (fallback for every locale); any other
# language code (e.g. "es") is sent for that specific locale.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(dirname "$here")"

if [[ -f "$root/.env" ]]; then
  set -a; . "$root/.env"; set +a
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  echo "TELEGRAM_BOT_TOKEN is not set (put it in .env)." >&2
  exit 1
fi

api="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}"

# apply <method> <param> <file>
apply() {
  local method="$1" param="$2" file="$3"
  local base lang
  base="$(basename "$file")"
  lang="${base##*.}"            # placeholder, overwritten below
  lang="$(echo "$base" | sed -E 's/^[a-z_]+\.([a-z]+)\.txt$/\1/')"

  local args=(--data-urlencode "${param}@${file}")
  if [[ "$lang" != "en" ]]; then
    args+=(--data-urlencode "language_code=${lang}")
    echo "-> ${method} (${lang})"
  else
    echo "-> ${method} (default/en)"
  fi
  curl -fsS -X POST "${api}/${method}" "${args[@]}" >/dev/null
}

shopt -s nullglob
for f in "$here"/description.*.txt; do
  apply setMyDescription description "$f"
done
for f in "$here"/short_description.*.txt; do
  apply setMyShortDescription short_description "$f"
done

echo "Done."
