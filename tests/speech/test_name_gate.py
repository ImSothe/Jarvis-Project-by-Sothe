"""Local "does it start with Jarvis?" check used before the cloud transcription."""

from __future__ import annotations

import pytest

from openjarvis.speech.name_gate import mentions_name


@pytest.mark.parametrize(
    "text",
    [
        "Jarvis, pon música",
        "Oye Jarvis ábreme Spotify",
        "Vale, hola Jarvis sube el volumen",
        "Yarvis pon Quevedo",
        "Jarbis abre Discord",
        "Harvis, dime la hora.",
        "Charvis",
        "Jarvi",
        "¡JÁRVIS!",
    ],
)
def test_name_at_the_start_passes(text):
    assert mentions_name(text)


@pytest.mark.parametrize(
    "text",
    [
        "Ponme música tranquila por favor",
        "Ayer fui al cine con mi hermano",
        "Dile a Carlos que ya voy",
        "Hoy vamos a analizar este vídeo viral",
        "",
    ],
)
def test_other_speech_is_blocked(text):
    assert not mentions_name(text)


def test_name_far_into_the_sentence_does_not_count():
    assert not mentions_name("le dije a mi amigo Pedro que mañana por la tarde le hablaba de Jarvis")
