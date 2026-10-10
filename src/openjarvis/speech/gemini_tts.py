"""Gemini text-to-speech backend — native Gemini audio output (no separate
Kokoro/Cartesia/OpenAI TTS dependency)."""

from __future__ import annotations

import io
import os
import re
import wave
from typing import List

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None  # type: ignore[assignment]
    genai_types = None  # type: ignore[assignment]

_STYLE_MODEL = "gemini-3.1-flash-tts-preview"

# The 30 prebuilt voices documented for Gemini's native TTS models.
_VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]


def _wav_sample_rate(wav_bytes: bytes) -> int:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            return wf.getframerate()
    except Exception:
        return 24000


def _ensure_wav(data: bytes, mime_type: str) -> bytes:
    """Some Gemini TTS models return raw 16-bit mono PCM (mime like
    ``audio/L16;codec=pcm;rate=24000``) instead of a WAV file. Browsers cannot
    play raw PCM, which made the call fall back to the robotic browser voice.
    """
    if data[:4] == b"RIFF":
        return data
    rate = 24000
    match = re.search(r"rate=(\d+)", mime_type or "")
    if match:
        rate = int(match.group(1))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(data)
    return buf.getvalue()


@TTSRegistry.register("gemini_tts")
class GeminiTTSBackend(TTSBackend):
    """Text-to-speech using a Gemini native-audio model."""

    backend_id = "gemini_tts"

    # Tried in order; each model has its own free-tier quota, so a 429 on one
    # falls through to the next instead of leaving the call silent.
    _FALLBACK_MODELS = (
        "gemini-3.8-flash-lite-tts",
        "gemini-3.1-flash-tts-preview",
        "gemini-3.8-flash-tts",
    )

    def __init__(self, *, api_key: str = "", model: str = "") -> None:
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get(
            "GOOGLE_API_KEY", ""
        )
        self._model = model or os.environ.get("GEMINI_TTS_MODEL", self._FALLBACK_MODELS[0])
        self._client = None
        if self._api_key and genai is not None:
            self._client = genai.Client(api_key=self._api_key)

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "Kore",
        speed: float = 1.0,
        output_format: str = "wav",
    ) -> TTSResult:
        if self._client is None:
            raise RuntimeError("Gemini client not initialized (missing API key?)")

        voice = voice_id or "Kore"
        # Optional acting direction (GEMINI_TTS_STYLE), e.g. "Di con voz grave y seca". Only the
        # 3.1 preview TTS model follows it silently; the other models READ IT ALOUD, so they get
        # the plain text.
        style = os.environ.get("GEMINI_TTS_STYLE", "").strip()
        config = genai_types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=genai_types.SpeechConfig(
                voice_config=genai_types.VoiceConfig(
                    prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                        voice_name=voice
                    )
                )
            ),
        )
        first = _STYLE_MODEL if style else self._model
        models = [first] + [m for m in (self._model, *self._FALLBACK_MODELS) if m != first]
        models = list(dict.fromkeys(models))
        last_err: Exception | None = None
        for model in models:
            try:
                spoken = f"{style.rstrip(':')}: {text}" if style and model == _STYLE_MODEL else text
                response = self._client.models.generate_content(
                    model=model, contents=spoken, config=config
                )
                inline = response.candidates[0].content.parts[0].inline_data
                audio_bytes = _ensure_wav(inline.data, getattr(inline, "mime_type", "") or "")
            except Exception as exc:  # quota / transient errors: try next model
                last_err = exc
                continue
            return TTSResult(
                audio=audio_bytes,
                format="wav",
                voice_id=voice,
                sample_rate=_wav_sample_rate(audio_bytes),
                metadata={"backend": "gemini_tts", "model": model},
            )
        # Every Gemini model failed (quota...): try the Edge voice instead of going silent.
        try:
            from openjarvis.speech.edge_tts_voice import EdgeTTSBackend

            edge = EdgeTTSBackend()
            if edge.health():
                return edge.synthesize(text, speed=speed, _no_gemini_fallback=True)
        except Exception:
            pass
        raise last_err if last_err else RuntimeError("Gemini TTS failed")

    def available_voices(self) -> List[str]:
        return list(_VOICES)

    def health(self) -> bool:
        return self._client is not None and bool(self._api_key)
