"""Local check: does this audio start with the name Jarvis? Done before the cloud.

The voice loop sends every sentence the mic hears to the cloud speech-to-text, and
then ignores the ones that do not start with "Jarvis" (a reel, the TV, other people).
This runs a small local Whisper first and only lets the audio through when the name is
heard at the start. It is deliberately permissive (accent-insensitive, anything shaped
like the name, fuzzy match): a false "yes" only costs the cloud call we would have made
anyway, a false "no" ignores the user.

Two passes keep it fast and accurate: the quick "base" model clears most real commands
in ~0.3 s; only when it does not hear the name does the slower, more accurate "small"
model double-check (~1 s, and nothing is waiting on a sentence about to be ignored).
Clips shorter than a second and a half always pass: a bare "Jarvis" is that short and
sending so little audio costs almost nothing.

If the local models cannot load or run, the gate fails open (returns ``None``) and
nothing changes.
"""

from __future__ import annotations

import difflib
import io
import logging
import os
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_QUICK, _ACCURATE = "base", "small"
# Anything that sounds like "Jarvis": "<letters>ar<consonant(s)>i/y(s/z)" (jarvis,
# yarvis, harvis, jarcis, martis, garbis, jarvi...) or "<letters>ar[vb]e(s/y/z)"
# (harvey, jarves). Deliberately loose: a false "yes" only costs the cloud call we
# would have made anyway, a false "no" ignores the user. Ordinary words such as
# parte or martes do not match (they end in -e / -es after a t).
_NAME_RE = re.compile(
    r"^(?:[a-z]{0,3}ar[bcdfgjklmnpqstvwxyz]{1,2}[iy]{1,2}[sz]?|[a-z]{0,3}ar[vb]e[syz]?)$"
)
# Letter-swapped mishearings (travis, cervis, servis, gervis) score ~0.67 against
# "jarvis". Ordinary words that slip through (jardin, varios) only cost a cloud call.
_FUZZY_MIN = 0.6
_MIN_SECONDS_TO_GATE = 1.5
_WORDS_CHECKED = 5  # "oye, vale, hola Jarvis ..." still counts as the start
_SAMPLE_RATE = 16000
_MAX_SECONDS = 4.0  # the name is at the start; no need to listen to the whole sentence
_CPU_THREADS = 8


@dataclass
class GateResult:
    heard_name: bool
    text: str


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def mentions_name(text: str) -> bool:
    """True if one of the first words of ``text`` looks like "Jarvis"."""
    words = re.findall(r"[a-z0-9]+", _normalize(text))[:_WORDS_CHECKED]
    return any(
        _NAME_RE.match(w)
        or difflib.SequenceMatcher(None, w, "jarvis").ratio() >= _FUZZY_MIN
        for w in words
    )


def _log(verdict: str, seconds: float, text: str) -> None:
    """Opt-in diagnostics: ``JARVIS_GATE_LOG=1`` appends what the local model heard.

    Stays on this PC (``~/.openjarvis/name_gate.log``), keeps only the first words and
    is truncated when it grows past ~200 KB. Use it to see why a "Jarvis" was missed.
    """
    if os.environ.get("JARVIS_GATE_LOG") != "1":
        return
    try:
        from openjarvis.core.config import DEFAULT_CONFIG_DIR

        path = DEFAULT_CONFIG_DIR / "name_gate.log"
        if path.exists() and path.stat().st_size > 200_000:
            path.write_text("", encoding="utf-8")
        words = " ".join(text.split()[:12])
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp} | {seconds:4.1f}s | {verdict:<13} | {words}\n")
    except Exception:  # noqa: BLE001 - diagnostics must never affect the voice loop
        pass


class NameGate:
    def __init__(self) -> None:
        self._models: Dict[str, object] = {}
        self._failed = False
        # One clip at a time; the models are not meant for concurrent use.
        self._lock = threading.Lock()

    def _model(self, size: str):
        if size not in self._models:
            from faster_whisper import WhisperModel

            # CPU + int8: no CUDA libraries needed.
            self._models[size] = WhisperModel(
                size, device="cpu", compute_type="int8", cpu_threads=_CPU_THREADS
            )
        return self._models[size]

    def _transcribe(self, size: str, audio) -> str:
        # No initial_prompt: priming with "Jarvis" made Whisper drop the word.
        segments, _ = self._model(size).transcribe(
            audio,
            language="es",
            beam_size=1,
            condition_on_previous_text=False,
            without_timestamps=True,
        )
        return "".join(s.text for s in segments).strip()

    def check(self, audio: bytes) -> Optional[GateResult]:
        """``GateResult``, or ``None`` when the local models are unavailable."""
        if self._failed:
            return None
        with self._lock:
            try:
                from faster_whisper.audio import decode_audio

                samples = decode_audio(io.BytesIO(audio), sampling_rate=_SAMPLE_RATE)
                seconds = len(samples) / _SAMPLE_RATE
                if seconds < _MIN_SECONDS_TO_GATE:
                    _log("PASS (short)", seconds, "")
                    return GateResult(heard_name=True, text="")
                samples = samples[: int(_MAX_SECONDS * _SAMPLE_RATE)]
                text = self._transcribe(_QUICK, samples)
                if not mentions_name(text):
                    text = self._transcribe(_ACCURATE, samples)
            except ImportError as exc:
                logger.warning(
                    "Name gate unavailable (%s); sending all speech to the cloud", exc
                )
                self._failed = True
                return None
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Name gate failed on a clip (%s); letting it through", exc
                )
                return None
        heard = mentions_name(text)
        _log("PASS" if heard else "BLOCK", seconds, text)
        return GateResult(heard_name=heard, text=text)


_gate = NameGate()


def warm_up() -> None:
    """Load both models in the background; never raises."""
    try:
        with _gate._lock:
            _gate._model(_QUICK)
            _gate._model(_ACCURATE)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Name gate warm-up failed (%s); it will retry on first use", exc)


def check_name(audio: bytes, fmt: str = "webm") -> Optional[GateResult]:
    """``fmt`` is kept for the caller's convenience; the decoder detects the format."""
    return _gate.check(audio)
