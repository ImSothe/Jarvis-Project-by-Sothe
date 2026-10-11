"""Play and control Spotify through the official Web API (needs Premium).

Uses the OAuth tokens saved by ``jarvis connect spotify`` in
``~/.openjarvis/connectors/spotify.json`` and refreshes the access token when it
expires (it lasts one hour). Playback happens on one of Sothe's own devices; if
the desktop app is closed it is started and we wait for the device to appear.

Tools:
  spotify_play     liked songs (shuffled by default), an artist, track, album or
                   playlist found by search, or resume.
  spotify_control  pause, resume, next, previous, volume, shuffle, now_playing, like.
"""

from __future__ import annotations

import difflib
import json
import os
import random
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from openjarvis.core.config import DEFAULT_CONFIG_DIR
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec
from openjarvis.tools._text import clean_query

_API = "https://api.spotify.com/v1"
_TOKEN_URL = "https://accounts.spotify.com/api/token"
_TOKEN_FILE = DEFAULT_CONFIG_DIR / "connectors" / "spotify.json"
_DEVICE_WAIT_S = 20


class SpotifyError(Exception):
    """A problem worth telling the user about in plain words."""


# --------------------------------------------------------------------------- auth

def _load() -> Dict[str, str]:
    try:
        data = json.loads(Path(_TOKEN_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SpotifyError("Spotify is not connected. Run: jarvis-terminal connect spotify")
    if not data.get("access_token") and not data.get("refresh_token"):
        raise SpotifyError("Spotify is not connected. Run: jarvis-terminal connect spotify")
    return data


def _save(data: Dict[str, str]) -> None:
    path = Path(_TOKEN_FILE)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _refresh(data: Dict[str, str]) -> Dict[str, str]:
    if not (data.get("refresh_token") and data.get("client_id") and data.get("client_secret")):
        raise SpotifyError("Spotify login expired and cannot be renewed. Run: jarvis-terminal connect spotify")
    resp = httpx.post(
        _TOKEN_URL,
        data={"grant_type": "refresh_token", "refresh_token": data["refresh_token"]},
        auth=(data["client_id"], data["client_secret"]),
        timeout=30.0,
    )
    if resp.status_code >= 400:
        raise SpotifyError("Spotify login expired. Run: jarvis-terminal connect spotify")
    fresh = resp.json()
    data = {**data, "access_token": fresh["access_token"]}
    if fresh.get("refresh_token"):
        data["refresh_token"] = fresh["refresh_token"]
    _save(data)
    return data


def _call(method: str, path: str, *, params: Optional[Dict[str, Any]] = None,
          body: Optional[Dict[str, Any]] = None) -> httpx.Response:
    data = _load()
    if not data.get("access_token"):
        data = _refresh(data)
    for attempt in (0, 1):
        resp = httpx.request(
            method, f"{_API}/{path.lstrip('/')}", params=params, json=body,
            headers={"Authorization": f"Bearer {data['access_token']}"}, timeout=30.0,
        )
        if resp.status_code == 401 and attempt == 0:
            data = _refresh(data)
            continue
        break
    return resp


def _error_text(resp: httpx.Response) -> str:
    try:
        err = resp.json().get("error", {})
        msg = err.get("message", "") if isinstance(err, dict) else str(err)
        reason = err.get("reason", "") if isinstance(err, dict) else ""
    except ValueError:
        msg, reason = resp.text[:120], ""
    if resp.status_code == 403 and ("premium" in msg.lower() or reason == "PREMIUM_REQUIRED"):
        return "Spotify says playback control needs a Premium account."
    if resp.status_code == 403:
        return ("Spotify refused (403). Check that the app has the playback permissions "
                "(reconnect with jarvis-terminal connect spotify) and that your account is "
                f"added under User Management in the Spotify dashboard. Detail: {msg}")
    if reason == "NO_ACTIVE_DEVICE" or resp.status_code == 404:
        return "No active Spotify device. Open Spotify on the PC and try again."
    return f"Spotify error {resp.status_code}: {msg}"


def _ok(resp: httpx.Response) -> None:
    if resp.status_code >= 400:
        raise SpotifyError(_error_text(resp))


# ------------------------------------------------------------------------ devices

def _devices() -> List[Dict[str, Any]]:
    resp = _call("GET", "me/player/devices")
    _ok(resp)
    return resp.json().get("devices", [])


def _start_desktop_app() -> None:
    if sys.platform == "win32":
        try:
            os.startfile("spotify:")  # type: ignore[attr-defined]  # noqa: S606
        except OSError:
            pass


def _pick_device() -> Tuple[str, str]:
    """Return (device_id, name) for playback.

    Always the PC's own Spotify app (type "Computer"), even if another device
    such as a TV is the last active one. If the PC app is not running we start
    it and wait. Never falls back to a TV or speaker: playing on a Connect
    device in another room would be a nasty surprise.
    """
    deadline = time.time() + _DEVICE_WAIT_S
    started = False
    while True:
        devs = [d for d in _devices() if d.get("id") and not d.get("is_restricted")]
        chosen = next((d for d in devs if str(d.get("type", "")).lower() == "computer"), None)
        if chosen:
            return chosen["id"], chosen.get("name", "device")
        if not started:
            _start_desktop_app()
            started = True
        if time.time() >= deadline:
            others = ", ".join(f"{d.get('name')} ({d.get('type')})" for d in devs) or "none"
            raise SpotifyError(
                "The Spotify app on the PC did not show up as a device, so I did not play anything "
                f"(other devices seen: {others}). Open Spotify on the PC and try again."
            )
        time.sleep(2)


def _clean_query(text: Any) -> str:
    return clean_query(text, 80)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _track_label(item: Dict[str, Any]) -> str:
    name = item.get("name", "")
    artists = " ".join(a.get("name", "") for a in item.get("artists", []))
    return f"{name} {artists}".strip()


def _best_match(query: str, items: List[Dict[str, Any]], label_fn) -> Tuple[Dict[str, Any], float]:
    """Spotify's search already ranks by relevance, but a very popular item with an
    unrelated name can still outrank the one actually being asked for (this is the
    main cause of "ponme X" playing something random). Re-score the handful of
    candidates it returns by plain text similarity to what was actually asked for,
    and only let Spotify's own ranking break ties.
    """
    scored = [(item, _similarity(query, label_fn(item))) for item in items]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[0]


# ------------------------------------------------------------------------- tools

class _SpotifyTool(BaseTool):
    def _ok_result(self, text: str, **meta: Any) -> ToolResult:
        return ToolResult(tool_name=self.tool_id, content=text, success=True, metadata=meta)

    def _fail(self, text: str) -> ToolResult:
        return ToolResult(tool_name=self.tool_id, content=text, success=False)


@ToolRegistry.register("spotify_play")
class SpotifyPlayTool(_SpotifyTool):
    tool_id = "spotify_play"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="spotify_play",
            description=(
                "Use this for ANY request to play music, an artist, a song or his favourites, even when he says 'abre Spotify y pon X' (it starts the app by itself, so do not call open_app first). what='liked' plays his Liked Songs "
                "(shuffled unless shuffle=false); what='artist'|'track'|'album'|'playlist' searches "
                "'query' and plays the best match; what='resume' continues what was playing. "
                "Starts the Spotify app if it is closed. Report the exact song or artist the tool "
                "says it started; do not guess."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "what": {"type": "string", "enum": ["liked", "artist", "track", "album", "playlist", "resume"]},
                    "query": {"type": "string", "description": "Search text for artist/track/album/playlist."},
                    "shuffle": {"type": "boolean", "description": "Shuffle (default true for liked songs)."},
                },
                "required": ["what"],
            },
            category="media",
            timeout_seconds=60.0,
        )

    def execute(self, **p: Any) -> ToolResult:
        what = str(p.get("what", "")).strip().lower()
        try:
            device_id, device_name = _pick_device()
            if what == "resume":
                _ok(_call("PUT", "me/player/play", params={"device_id": device_id}))
                return self._ok_result(f"Resumed playback on {device_name}.")
            if what == "liked":
                return self._play_liked(device_id, device_name, p.get("shuffle", True))
            if what in ("artist", "track", "album", "playlist"):
                return self._play_search(device_id, device_name, what, _clean_query(p.get("query")),
                                         p.get("shuffle"))
            return self._fail("Unknown 'what'. Use liked, artist, track, album, playlist or resume.")
        except SpotifyError as exc:
            return self._fail(str(exc))
        except httpx.HTTPError as exc:
            return self._fail(f"Network problem talking to Spotify: {exc}")

    def _set_shuffle(self, device_id: str, on: bool) -> None:
        _call("PUT", "me/player/shuffle", params={"state": str(on).lower(), "device_id": device_id})

    def _play_liked(self, device_id: str, device_name: str, shuffle: Any) -> ToolResult:
        shuffle = True if shuffle is None else bool(shuffle)
        head = _call("GET", "me/tracks", params={"limit": 1})
        _ok(head)
        total = int(head.json().get("total", 0))
        if total == 0:
            return self._fail("Your Liked Songs list is empty (or the permission is missing).")
        limit = min(50, total)
        offset = random.randint(0, max(0, total - limit)) if shuffle else 0
        page = _call("GET", "me/tracks", params={"limit": limit, "offset": offset})
        _ok(page)
        items = [it["track"] for it in page.json().get("items", []) if it.get("track") and it["track"].get("uri")]
        if shuffle:
            random.shuffle(items)
        uris = [t["uri"] for t in items][:50]
        _ok(_call("PUT", "me/player/play", params={"device_id": device_id}, body={"uris": uris}))
        self._set_shuffle(device_id, shuffle)
        first = items[0]
        who = ", ".join(a["name"] for a in first.get("artists", [])[:2])
        return self._ok_result(
            f"Playing your Liked Songs ({'shuffled' if shuffle else 'in order'}) on {device_name}. "
            f"First track: {first.get('name')} - {who}. ({total} liked songs in total.)",
            first_track=first.get("name"),
        )

    def _play_search(self, device_id: str, device_name: str, kind: str, query: str, shuffle: Any) -> ToolResult:
        if not query:
            return self._fail("A search text is required in 'query'.")
        resp = _call("GET", "search", params={"q": query, "type": kind, "limit": 5})
        if resp.status_code == 400:  # some app tiers cap the limit
            resp = _call("GET", "search", params={"q": query, "type": kind, "limit": 1})
        _ok(resp)
        items = [i for i in resp.json().get(f"{kind}s", {}).get("items", []) if i]
        if not items:
            return self._fail(f"I found no {kind} for '{query}' on Spotify.")
        # Re-rank by text similarity to what was actually asked (see _best_match): Spotify's own
        # relevance order sometimes puts a famous, unrelated result above the one being asked for.
        label_fn = _track_label if kind in ("track", "album") else lambda it: it.get("name", "")
        top, score = _best_match(query, items, label_fn)
        body = {"uris": [top["uri"]]} if kind == "track" else {"context_uri": top["uri"]}
        _ok(_call("PUT", "me/player/play", params={"device_id": device_id}, body=body))
        if shuffle is not None and kind != "track":
            self._set_shuffle(device_id, bool(shuffle))
        label = top.get("name", query)
        if kind in ("track", "album"):
            artists = ", ".join(a["name"] for a in top.get("artists", [])[:2])
            label = f"{label} - {artists}" if artists else label
        # Low similarity: the match is a guess (often because the query itself was likely
        # mis-transcribed), so say so plainly instead of presenting it as a confident pick.
        if score < 0.45:
            return self._ok_result(
                f"Not fully sure I understood '{query}' right, closest {kind} I found: '{label}' on {device_name}. "
                "If that's not it, say the name again more clearly or spell it out.",
                uri=top["uri"], match_confidence=score,
            )
        return self._ok_result(f"Playing {kind} '{label}' on {device_name}.", uri=top["uri"], match_confidence=score)


@ToolRegistry.register("spotify_control")
class SpotifyControlTool(_SpotifyTool):
    tool_id = "spotify_control"
    _ACTIONS = ("pause", "resume", "next", "previous", "volume", "shuffle", "now_playing", "like")

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="spotify_control",
            description=(
                "Control Sothe's current Spotify playback: pause, resume, next, previous, "
                "volume (percent 0-100), shuffle (on true/false - use this for 'pon aleatorio'/'modo "
                "aleatorio'/shuffle mode, even with nothing else requested), now_playing (what is "
                "playing right now), and like (save a song to his Liked Songs / Favorites - 'ponlo en "
                "favoritos', 'dale a me gusta', 'guarda esta cancion'). like with no 'query' saves the "
                "song currently playing; with 'query' it searches that track and saves it instead, "
                "without changing playback. Prefer this over media_control when Spotify is the player."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": list(self._ACTIONS)},
                    "percent": {"type": "integer", "description": "Volume 0-100 for action=volume."},
                    "on": {"type": "boolean", "description": "For action=shuffle."},
                    "query": {"type": "string", "description": "Optional track search text for action=like; omit to like the song currently playing."},
                },
                "required": ["action"],
            },
            category="media",
        )

    def execute(self, **p: Any) -> ToolResult:
        action = str(p.get("action", "")).strip().lower()
        if action not in self._ACTIONS:
            return self._fail(f"Unknown action. Allowed: {', '.join(self._ACTIONS)}.")
        try:
            if action == "now_playing":
                resp = _call("GET", "me/player/currently-playing")
                if resp.status_code == 204:
                    return self._ok_result("Nothing is playing right now.")
                _ok(resp)
                data = resp.json()
                item = data.get("item") or {}
                if not item:
                    return self._ok_result("Nothing is playing right now.")
                who = ", ".join(a["name"] for a in item.get("artists", [])[:3])
                state = "Playing" if data.get("is_playing") else "Paused on"
                return self._ok_result(f"{state}: {item.get('name')} - {who}.")
            if action == "pause":
                _ok(_call("PUT", "me/player/pause"))
                return self._ok_result("Paused.")
            if action == "resume":
                _ok(_call("PUT", "me/player/play"))
                return self._ok_result("Resumed.")
            if action in ("next", "previous"):
                _ok(_call("POST", f"me/player/{action}"))
                return self._ok_result(f"Skipped to the {action} track.")
            if action == "volume":
                try:
                    pct = int(p.get("percent"))
                except (TypeError, ValueError):
                    return self._fail("percent (0-100) is required for volume.")
                pct = max(0, min(100, pct))
                _ok(_call("PUT", "me/player/volume", params={"volume_percent": pct}))
                return self._ok_result(f"Volume set to {pct}%.")
            if action == "like":
                return self._like(str(p.get("query", "") or "").strip())
            on = bool(p.get("on", True))
            _ok(_call("PUT", "me/player/shuffle", params={"state": str(on).lower()}))
            return self._ok_result(f"Shuffle {'on' if on else 'off'}.")
        except SpotifyError as exc:
            return self._fail(str(exc))
        except httpx.HTTPError as exc:
            return self._fail(f"Network problem talking to Spotify: {exc}")

    def _like(self, query: str) -> ToolResult:
        if query:
            resp = _call("GET", "search", params={"q": _clean_query(query), "type": "track", "limit": 5})
            _ok(resp)
            items = [i for i in resp.json().get("tracks", {}).get("items", []) if i]
            if not items:
                return self._fail(f"I found no track for '{query}' on Spotify.")
            track, score = _best_match(query, items, _track_label)
        else:
            resp = _call("GET", "me/player/currently-playing")
            if resp.status_code == 204:
                return self._fail("Nothing is playing right now, and no 'query' was given to search a track.")
            _ok(resp)  # raises/reports the real error for 401/403/5xx instead of masking it as "nothing playing"
            item = resp.json().get("item")
            if not item:
                return self._fail("Nothing is playing right now, and no 'query' was given to search a track.")
            track, score = item, 1.0
        label = _track_label(track)
        _ok(_call("PUT", "me/tracks", params={"ids": track["id"]}))
        if query and score < 0.45:
            return self._ok_result(
                f"Not fully sure I understood '{query}' right; saved the closest match to Liked Songs: '{label}'.",
                track_id=track["id"], match_confidence=score,
            )
        return self._ok_result(f"Added '{label}' to your Liked Songs.", track_id=track["id"])
