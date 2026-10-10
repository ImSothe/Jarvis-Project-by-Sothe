"""Edge neural voices (Microsoft) as a TTS backend: a fixed Spanish-from-Spain voice.

Why: Gemini's free TTS quota runs out quickly and its voice changes with the model
and the fallback path. A neural Edge voice is the same voice every time, needs no
API key and has no per-day quota. Default: ``es-ES-AlvaroNeural`` (male, Spain).

Caveat: it uses the read-aloud service that Microsoft Edge uses; it is not an
official public API, so it needs internet and could stop working. If a request
fails, the call falls back to Gemini TTS (another voice) instead of going silent.

Requires: pip install edge-tts
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import List

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "es-ES-AlvaroNeural"
_VOICE_RE = re.compile(r"^[a-z]{2,3}-[A-Z]{2}-[A-Za-z]+Neural$")
_TIMEOUT_S = 25.0
_RETRY_AFTER_S = 300.0   # after a failure skip Edge for a while instead of paying its timeout every sentence
_down_until = 0.0
_PITCH_RE = re.compile(r"^[+-]\d{1,2}Hz$")


def _pitch() -> str:
    """Optional deeper/higher tone from OPENJARVIS_EDGE_PITCH (e.g. -12Hz); default untouched."""
    value = os.environ.get("OPENJARVIS_EDGE_PITCH", "").strip()
    return value if _PITCH_RE.match(value) else "+0Hz"


def _clean(text: str) -> str:
    """Drop markdown and emoji-ish symbols that the voice would read aloud."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"[`*_#>~|]+", " ", text)
    text = re.sub(r"https?://\S+", " enlace ", text)
    text = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@TTSRegistry.register("edge_tts")
class EdgeTTSBackend(TTSBackend):
    """Spanish (Spain) male neural voice, identical on every call."""

    backend_id = "edge_tts"

    def __init__(self) -> None:
        self._ok = False
        try:
            import edge_tts  # noqa: F401

            self._ok = True
        except ImportError:
            logger.debug("edge-tts is not installed")

    def health(self) -> bool:
        return self._ok

    def available_voices(self) -> List[str]:
        return [DEFAULT_VOICE]

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        speed: float = 1.0,
        output_format: str = "mp3",
        _no_gemini_fallback: bool = False,
    ) -> TTSResult:
        voice = voice_id if _VOICE_RE.match(voice_id or "") else DEFAULT_VOICE
        spoken = _clean(text)
        if not spoken:
            raise ValueError("Nothing to say after cleaning the text")
        global _down_until
        if time.time() < _down_until:
            if _no_gemini_fallback:
                raise RuntimeError("Edge TTS is temporarily down")
            return self._gemini_fallback(spoken)
        try:
            audio = self._edge(spoken, voice, speed)
            return TTSResult(
                audio=audio, format="mp3", voice_id=voice, sample_rate=24000,
                metadata={"backend": "edge_tts"},
            )
        except Exception as exc:
            _down_until = time.time() + _RETRY_AFTER_S
            logger.warning("Edge TTS failed (%s); using Gemini TTS for the next %d s", exc, int(_RETRY_AFTER_S))
            if _no_gemini_fallback:
                raise
            return self._gemini_fallback(spoken)

    @staticmethod
    def _edge(text: str, voice: str, speed: float) -> bytes:
        import edge_tts

        rate = f"{int(round((max(0.5, min(2.0, speed)) - 1.0) * 100)):+d}%"
        pitch = _pitch()

        async def run() -> bytes:
            chunks: List[bytes] = []
            async for part in edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).stream():
                if part["type"] == "audio":
                    chunks.append(part["data"])
            return b"".join(chunks)

        # Called from a worker thread (no running loop), so asyncio.run is safe.
        data = asyncio.run(asyncio.wait_for(run(), timeout=_TIMEOUT_S))
        if not data:
            raise RuntimeError("Edge returned no audio")
        return data

    @staticmethod
    def _gemini_fallback(text: str) -> TTSResult:
        from openjarvis.speech.gemini_tts import GeminiTTSBackend

        backend = GeminiTTSBackend()
        if not backend.health():
            raise RuntimeError("Edge TTS failed and Gemini TTS is not available")
        return backend.synthesize(text, voice_id=os.environ.get("OPENJARVIS_FALLBACK_VOICE", "Charon"))  # a male Gemini voice
