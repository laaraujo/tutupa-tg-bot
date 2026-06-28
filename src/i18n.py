"""Minimal i18n for the bot's user-facing strings (English / Spanish).

English is the default and the fallback for any unknown locale.
"""

DEFAULT_LANG = "en"

# Translated stem names per language. Falls back to the raw stem id (e.g.
# "drums") if a language or stem isn't listed.
_STEM_NAMES = {
    "en": {"drums": "drums", "bass": "bass", "vocals": "vocals", "other": "other"},
    "es": {"drums": "batería", "bass": "bajo", "vocals": "voces", "other": "lo demás"},
}

_MESSAGES = {
    "help": {
        "en": (
            "Send me either:\n"
            "\u2022 an audio file (mp3, m4a, wav, ...), or\n"
            "\u2022 a Spotify track link (https://open.spotify.com/track/...)\n\n"
            "and I'll split it into:\n"
            "\u2022 {stem}\n"
            "\u2022 everything else (the mix without {stem})\n"
            "\u2022 {stem} emphasized ({stem} at 100%, everything else at 50%)\n\n"
            "Uploaded files must be under 20 MB; Spotify links have no such limit."
        ),
        "es": (
            "Envíame:\n"
            "\u2022 un archivo de audio (mp3, m4a, wav, ...), o\n"
            "\u2022 el enlace de una canción de Spotify "
            "(https://open.spotify.com/track/...)\n\n"
            "y lo separaré en:\n"
            "\u2022 {stem}\n"
            "\u2022 todo lo demas (la mezcla sin {stem})\n"
            "\u2022 {stem} resaltada ({stem} al 100%, todo lo demas al 50%)\n\n"
            "Los archivos subidos deben pesar menos de 20 MB; los enlaces de "
            "Spotify no tienen ese límite."
        ),
    },
    "please_send_audio": {
        "en": "Please send an audio file (mp3, m4a, wav, ...).",
        "es": "Por favor envía un archivo de audio (mp3, m4a, wav, ...).",
    },
    "send_audio_or_link": {
        "en": (
            "Send me an audio file or a Spotify track link "
            "(https://open.spotify.com/track/...)."
        ),
        "es": (
            "Envíame un archivo de audio o el enlace de una canción de Spotify "
            "(https://open.spotify.com/track/...)."
        ),
    },
    "too_large": {
        "en": (
            "That file is too large (over 20 MB). Try a shorter clip, a lower "
            "bitrate, or send a Spotify link instead."
        ),
        "es": (
            "Ese archivo es demasiado grande (más de 20 MB). Prueba con un clip "
            "más corto, menor calidad, o envía un enlace de Spotify."
        ),
    },
    "downloading": {
        "en": "Got it - downloading...",
        "es": "¡Listo! Descargando...",
    },
    "fetching_spotify": {
        "en": "Got it - fetching the track from Spotify...",
        "es": "¡Listo! Obteniendo la canción de Spotify...",
    },
    "queued": {
        "en": "Queued - another track is processing...",
        "es": "En cola: se está procesando otra pista...",
    },
    "separating": {
        "en": "Separating {stem}...",
        "es": "Separando {stem}...",
    },
    "uploading": {
        "en": "Done - uploading tracks...",
        "es": "Listo: subiendo las pistas...",
    },
    "failed_separation": {
        "en": "Sorry, I couldn't separate that track. Please try again.",
        "es": "Lo siento, no pude separar esa pista. Inténtalo de nuevo.",
    },
    "failed_download": {
        "en": (
            "Couldn't download that track. Make sure it's a valid Spotify track "
            "link (not an album/playlist)."
        ),
        "es": (
            "No pude descargar esa canción. Asegúrate de que sea un enlace válido "
            "de una canción de Spotify (no un álbum ni una playlist)."
        ),
    },
    "error": {
        "en": "Something went wrong. Please try again.",
        "es": "Algo salió mal. Inténtalo de nuevo.",
    },
    "title_isolated": {
        "en": "{stem_cap}",
        "es": "{stem_cap}",
    },
    "title_everything": {
        "en": "Everything else",
        "es": "Todo lo demas",
    },
    "title_emphasis": {
        "en": "{stem_cap} emphasized",
        "es": "{stem_cap} resaltada",
    },
}


def resolve_lang(language_code: str | None) -> str:
    """Map a Telegram language_code to a supported language ("en"/"es")."""
    if language_code and language_code.lower().startswith("es"):
        return "es"
    return DEFAULT_LANG


def stem_label(lang: str, stem: str) -> str:
    """Return the localized name for a stem id (e.g. drums -> batería)."""
    return _STEM_NAMES.get(lang, _STEM_NAMES[DEFAULT_LANG]).get(stem, stem)


def t(lang: str, key: str, **kwargs) -> str:
    """Look up a message by key and language, formatting with kwargs.

    Extra kwargs are ignored, so callers can pass a common set (stem, stem_cap)
    to every message regardless of whether a given string uses them.
    """
    table = _MESSAGES[key]
    template = table.get(lang, table[DEFAULT_LANG])
    return template.format(**kwargs)
