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
            "\u2022 a Spotify track link\n\n"
            "and I'll split it into:\n"
            "\u2022 Just {stem}\n"
            "\u2022 No {stem}\n"
            "\u2022 {stem} emphasized\n\n"
            "Any of them can start with a one-bar metronome count-in.\n\n"
            "Uploaded files must be under 20 MB; Spotify links have no such limit."
        ),
        "es": (
            "Envíame:\n"
            "\u2022 un archivo de audio (mp3, m4a, wav, ...), o\n"
            "\u2022 el enlace de una canción de Spotify "
            "y lo separaré en:\n"
            "\u2022 Solo{stem}\n"
            "\u2022 Sin {stem}\n"
            "\u2022 {stem} resaltada\n\n"
            "Cualquiera puede empezar con un compás de conteo de metrónomo.\n\n"
            "Los archivos subidos deben pesar menos de 20 MB; los enlaces de "
            "Spotify no tienen ese límite."
        ),
    },
    "choose_outputs": {
        "en": (
            "Which track(s) do you want? Tap to select one or more, "
            "then press Send."
        ),
        "es": (
            "¿Qué pista(s) querés? Tocá para elegir una o más y luego "
            "presioná Enviar."
        ),
    },
    "btn_all": {
        "en": "Select all",
        "es": "Seleccionar todo",
    },
    "btn_send": {
        "en": "Send",
        "es": "Enviar",
    },
    "select_at_least_one": {
        "en": "Select at least one track first.",
        "es": "Elegí al menos una pista primero.",
    },
    "request_expired": {
        "en": "This request expired. Please send the song again.",
        "es": "Esta solicitud expiró. Envía la canción de nuevo.",
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
    "searching_alternative": {
        "en": "The usual source didn't work - looking for an alternative version... This will take a little longer than usual.",
        "es": "La fuente habitual no funcionó: buscando una versión alternativa... Esto tomará un poco más de tiempo que de costumbre.",
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
        "en": "Just {stem}",
        "es": "Solo {stem}",
    },
    "title_everything": {
        "en": "No {stem}",
        "es": "Sin {stem}",
    },
    "title_emphasis": {
        "en": "{stem_cap} emphasized",
        "es": "{stem_cap} resaltada",
    },
    "count_suffix": {
        "en": "+ count",
        "es": "+ conteo",
    },
    "ask_count": {
        "en": "Add a one-bar metronome count-in at the start of the track(s)?",
        "es": "¿Agregar un compás de conteo de metrónomo al inicio de la(s) pista(s)?",
    },
    "btn_yes": {
        "en": "Yes",
        "es": "Sí",
    },
    "btn_no": {
        "en": "No",
        "es": "No",
    },
    "ask_bpm": {
        "en": "What BPM is the song? Send a number, for example 120.",
        "es": "¿A qué BPM está la canción? Enviá un número, por ejemplo 120.",
    },
    "ask_bpm_invalid": {
        "en": "Send a BPM between 40 and 300, for example 120.",
        "es": "Enviá un BPM entre 40 y 300, por ejemplo 120.",
    },
    "ask_beats": {
        "en": "How many beats are in each bar? For example 4.",
        "es": "¿Cuántos tiempos tiene cada compás? Por ejemplo 4.",
    },
    "ask_beats_invalid": {
        "en": "Send a whole number of beats per bar, from 1 to 16.",
        "es": "Enviá un número entero de tiempos por compás, entre 1 y 16.",
    },
    "ask_start": {
        "en": (
            "On which beat does the song start? Send 1 if it starts on the "
            "downbeat, or 3 if it comes in on beat 3."
        ),
        "es": (
            "¿En qué tiempo entra la canción? Enviá 1 si entra en el primer "
            "tiempo, o 3 si entra en el 3."
        ),
    },
    "ask_start_invalid": {
        "en": "Send a beat from 1 to {beats}.",
        "es": "Enviá un tiempo del 1 al {beats}.",
    },
    "adding_count": {
        "en": "Adding the count-in...",
        "es": "Agregando el conteo...",
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
