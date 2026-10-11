"""Local check "does this audio start with the name Jarvis?", before paying for a cloud transcription.

The voice loop sends every sentence the mic hears to the cloud speech-to-text, and then ignores
the ones that do not start with "Jarvis" (a reel, the TV, other people). This runs a small local
Whisper first and only lets the audio through when the name is heard at the start. It is
deliberately permissive (accent-insensitive, misspellings like yarvis/jarbis, fuzzy match): a false
"yes" only costs the cloud call we would have made anyway, a false "no" ignores the user.

If the local model cannot load or run, the gate fails open (returns ``None``) and nothing changes.
"""

from __future__ import annotations

import difflib
import logging
import os
import re
import tempfile
import threading
import unicodedata
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# "small" heard the name in every test clip (~1 s on CPU); "base" is 3x faster but missed some.
_MODEL_SIZE = os.environ.get("JARVIS_GATE_MODEL", "small")
_NAME_RE = re.compile(r"^(?:j|y|h|g|ch)?ar[vb](?:[iy]s?|[iy]z|[iy])$")
_FUZZY_MIN = 0.7
_WORDS_CHECKED = 5  # "oye, vale, hola Jarvis ..." still counts as the start


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
        _NAME_RE.match(w) or difflib.SequenceMatcher(None, w, "jarvis").ratio() >= _FUZZY_MIN
        for w in words
    )


class NameGate:
    def __init__(self, model_size: str = _MODEL_SIZE) -> None:
        self._model_size = model_size
        self._model = None
        self._failed = False
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None and not self._failed:
            try:
                from faster_whisper import WhisperModel

                # CPU + int8: a few hundred ms for a short clip, and no CUDA libraries needed.
                self._model = WhisperModel(self._model_size, device="cpu", compute_type="int8")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Name gate unavailable (%s); sending all speech to the cloud", exc)
                self._failed = True
        return self._model

    def check(self, audio: bytes, fmt: str = "webm") -> Optional[GateResult]:
        """``GateResult`` or ``None`` when the local model is unavailable (fail open)."""
        with self._lock:  # one clip at a time; the model is not meant for concurrent use
            model = self._load()
            if model is None:
                return None
            # delete=False: an open NamedTemporaryFile cannot be reopened by PyAV on Windows.
            tmp = tempfile.NamedTemporaryFile(suffix=f".{fmt.lstrip('.')}", delete=False)
            try:
                with tmp:
                    tmp.write(audio)
                # No initial_prompt: priming with "Jarvis" made Whisper drop the word on some clips.
                segments, _ = model.transcribe(
                    tmp.name, language="es", beam_size=1, condition_on_previous_text=False,
                )
                text = "".join(s.text for s in segments).strip()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Name gate failed on a clip (%s); letting it through", exc)
                return None
            finally:
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass
        return GateResult(heard_name=mentions_name(text), text=text)


_gate = NameGate()


def check_name(audio: bytes, fmt: str = "webm") -> Optional[GateResult]:
    return _gate.check(audio, fmt)
