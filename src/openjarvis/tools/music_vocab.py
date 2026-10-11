"""Artists Sothe listens to, so speech recognition and Spotify searches get their names right.

Speech-to-text turns "Quevedo" into "Ponquevedos" or "pon que veo". Two fixes use this list:
the transcription prompt gets the exact spellings, and ``correct_query`` snaps a mangled artist
name back to the closest known one before searching. The list is built from the liked songs and
recent plays on Spotify (cached for a day) plus any names in ``music_vocab_extra.txt``.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
import threading
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import List

from openjarvis.core.config import DEFAULT_CONFIG_DIR

logger = logging.getLogger(__name__)

_CACHE = Path(DEFAULT_CONFIG_DIR) / "music_vocab.json"
_EXTRA = Path(DEFAULT_CONFIG_DIR) / "music_vocab_extra.txt"  # one name per line, optional
_MAX_AGE_S = 24 * 3600
_LIKED_PAGES = 4  # 4 x 50 most recent liked songs
_KEEP = 150

# Words around the artist in "ponme algo de Quevedo" that are not part of the name.
_FILLER = {
    "pon", "ponme", "ponlo", "ponla", "pone", "ponga", "reproduce", "reproduceme", "abre", "spotify",
    "en", "de", "del", "a", "algo", "musica", "cancion", "canciones", "artista", "la", "el", "lo",
    "me", "mi", "mis", "un", "una", "unas", "unos", "por", "favor", "quiero", "escuchar",
}
_MIN_SCORE = 0.82
_MIN_COVERAGE = 0.6  # the known name must account for most of what was said
_refresh_lock = threading.Lock()


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", " ", text).strip()


def _read_extra() -> List[str]:
    try:
        lines = _EXTRA.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]


def load_names(limit: int = 60) -> List[str]:
    """Known artist names, extras first, then the most listened to. Never raises."""
    names = _read_extra()
    try:
        names += json.loads(_CACHE.read_text(encoding="utf-8")).get("artists", [])
    except (OSError, ValueError):
        pass
    seen, out = set(), []
    for n in names:
        key = _norm(n)
        if key and key not in seen:
            seen.add(key)
            out.append(n)
    return out[:limit]


def correct_query(query: str) -> str:
    """Return the known artist name that ``query`` most likely means, else ``query`` unchanged."""
    core_words = [w for w in _norm(query).split() if w not in _FILLER]
    core = "".join(core_words)
    if len(core) < 4:
        return query
    best_name, best_score = None, 0.0
    for name in load_names(_KEEP):
        target = _norm(name).replace(" ", "")
        if len(target) < 4 or len(target) / len(core) < _MIN_COVERAGE:
            continue
        ratio = difflib.SequenceMatcher(None, core, target).ratio()
        # "ponquevedos": the name may sit inside extra glued-on letters.
        for size in (len(target) - 1, len(target), len(target) + 1):
            for i in range(max(1, len(core) - size + 1)):
                ratio = max(ratio, difflib.SequenceMatcher(None, core[i:i + size], target).ratio())
        if ratio > best_score:
            best_name, best_score = name, ratio
    if best_name is None or best_score < _MIN_SCORE:
        return query
    return best_name


def _build() -> List[str]:
    # Imported here: spotify_control imports this module.
    from openjarvis.tools import spotify_control as sp

    counts: Counter = Counter()

    def add(tracks) -> None:
        for track in tracks:
            for artist in (track or {}).get("artists", [])[:1]:  # main artist only
                if artist.get("name"):
                    counts[artist["name"]] += 1

    for page in range(_LIKED_PAGES):
        resp = sp._call("GET", "me/tracks", params={"limit": 50, "offset": page * 50})
        sp._ok(resp)
        items = resp.json().get("items", [])
        add(it.get("track") for it in items)
        if len(items) < 50:
            break
    resp = sp._call("GET", "me/player/recently-played", params={"limit": 50})
    sp._ok(resp)
    add(it.get("track") for it in resp.json().get("items", []))
    return [name for name, _ in counts.most_common(_KEEP)]


def refresh(force: bool = False) -> None:
    """Rebuild the cached list when it is older than a day. Safe to call from a thread."""
    if not _refresh_lock.acquire(blocking=False):
        return
    try:
        if not force and _CACHE.exists() and time.time() - _CACHE.stat().st_mtime < _MAX_AGE_S:
            return
        artists = _build()
        if artists:
            _CACHE.write_text(
                json.dumps({"updated": time.time(), "artists": artists}, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Music vocabulary refreshed: %d artists", len(artists))
    except Exception as exc:  # noqa: BLE001 - optional nicety, never break playback or startup
        logger.debug("Music vocabulary refresh skipped: %s", exc)
    finally:
        _refresh_lock.release()
