"""Local "does it start with Jarvis?" check used before the cloud transcription."""

from __future__ import annotations

import io
import wave

import pytest

from openjarvis.speech import name_gate
from openjarvis.speech.name_gate import NameGate, mentions_name


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
        # Whatever the recognizer writes for "Jarvis": anything like it must pass.
        "Jarcis pon música",
        "Travis pon música",
        "Martis abre Discord",
        "Cervis",
        "Servis, sube el volumen",
        "Gervis",
        "Tarvis",
        "Harvey",
        "Jarves dime la hora",
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
        "Quiero escuchar algo de Quevedo",
        "Gracias por todo, hasta mañana",
        "Hola buenos días a todos",
        "Esta parte del vídeo es importante",
        "El martes quedamos para cenar",
        "Dime las partes del informe",
        "",
    ],
)
def test_other_speech_is_blocked(text):
    assert not mentions_name(text)


def test_name_far_into_the_sentence_does_not_count():
    assert not mentions_name(
        "le dije a mi amigo Pedro que mañana por la tarde le hablaba de Jarvis"
    )


def _silence_wav(seconds: float) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buf.getvalue()


def test_very_short_clips_always_pass_without_loading_a_model():
    """A bare "Jarvis" is ~1 s: it must never be blocked and costs almost nothing."""
    gate = NameGate()
    result = gate.check(_silence_wav(0.8))
    assert result is not None and result.heard_name is True
    assert gate._models == {}  # no Whisper model was needed


def test_diagnostic_log_is_opt_in(monkeypatch, tmp_path):
    from openjarvis.core import config

    monkeypatch.setattr(config, "DEFAULT_CONFIG_DIR", tmp_path)
    log = tmp_path / "name_gate.log"

    monkeypatch.delenv("JARVIS_GATE_LOG", raising=False)
    name_gate._log("BLOCK", 2.0, "hola que tal")
    assert not log.exists()

    monkeypatch.setenv("JARVIS_GATE_LOG", "1")
    name_gate._log(
        "BLOCK", 2.0, "hola que tal estas hoy amigo mio como va todo por alli"
    )
    assert "BLOCK" in log.read_text(encoding="utf-8")
