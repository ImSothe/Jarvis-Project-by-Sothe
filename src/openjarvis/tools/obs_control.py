"""Control OBS Studio through its built-in WebSocket server (OBS 28+, port 4455).

Fixed list of actions; the model only picks an action name and, for scenes and
inputs, a name that must exist in OBS. Nothing else is sent to OBS. If OBS is
not running it is started from the path in ``~/.openjarvis/apps.json`` (entry
"obs") or the default install folder, then the tool waits for the socket.

Every action that changes state is verified by asking OBS again, so the result
text reports what OBS says, not what was requested. The WebSocket password (if
OBS has one) is read from OBS's own config at call time; it is never printed.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec
from openjarvis.tools.open_app import _load_apps

_ACTIONS = (
    "status", "start_stream", "stop_stream", "start_record", "stop_record",
    "list_scenes", "set_scene", "mute_mic", "unmute_mic", "launch",
)
_DEFAULT_EXE = r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"
_WS_CONFIG = Path(os.environ.get("APPDATA", "")) / "obs-studio" / "plugin_config" / "obs-websocket" / "config.json"
_HOST = "127.0.0.1"
logging.getLogger("obsws_python").setLevel(logging.CRITICAL)  # its tracebacks are noise while OBS boots


def _ws_settings() -> Dict[str, Any]:
    try:
        cfg = json.loads(_WS_CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}
    return {
        "port": int(cfg.get("server_port", 4455) or 4455),
        "password": str(cfg.get("server_password", "")) if cfg.get("auth_required") else "",
        "enabled": bool(cfg.get("server_enabled", True)),
    }


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection((_HOST, port), timeout=0.5):
            return True
    except OSError:
        return False


def _obs_exe() -> Optional[str]:
    entry = _load_apps().get("obs", {})
    for cand in (str(entry.get("path", "")), _DEFAULT_EXE):
        if cand and os.path.exists(cand):
            return cand
    return None


def _launch_obs() -> Optional[str]:
    exe = _obs_exe()
    if not exe:
        return "OBS is not installed in the default folder and has no 'obs' entry in apps.json."
    try:
        subprocess.Popen(  # noqa: S603 - fixed argv, no shell; OBS needs its own folder as cwd
            [exe, "--disable-shutdown-check"],
            cwd=str(Path(exe).parent), shell=False, close_fds=True,
            creationflags=0x00000008 | 0x00000200,
        )
    except OSError as exc:
        return f"Could not start OBS: {exc}"
    return None


def _connect(port: int, password: str, wait_s: float):
    import obsws_python as obs

    deadline = time.time() + wait_s
    last: Optional[Exception] = None
    while True:
        if _port_open(port):
            try:
                client = obs.ReqClient(host=_HOST, port=port, password=password, timeout=5)
                client.get_scene_list()  # OBS opens the socket before it finishes loading (error 207)
                return client
            except Exception as exc:  # socket up but OBS still loading, or wrong password
                last = exc
        if time.time() > deadline:
            raise RuntimeError(f"OBS did not answer on port {port}: {last or 'socket closed'}")
        time.sleep(0.7)


def _wait_until(check, seconds: float = 8.0) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        try:
            if check():
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


@ToolRegistry.register("obs_control")
class ObsControlTool(BaseTool):
    tool_id = "obs_control"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="obs_control",
            description=(
                "Control OBS Studio on Sothe's PC. Actions: launch (open OBS), status (is it "
                "live/recording, current scene), start_stream / stop_stream (going LIVE is public: "
                "only when Sothe explicitly asks for it, never on your own), start_record / "
                "stop_record, list_scenes, set_scene (needs 'name'), mute_mic / unmute_mic "
                "(optional 'name' of the audio input). If OBS is closed it is opened first. The "
                "result states what OBS reported afterwards; relay exactly that."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": list(_ACTIONS)},
                    "name": {"type": "string", "description": "Scene or input name, only for set_scene / mute_mic / unmute_mic."},
                },
                "required": ["action"],
            },
            category="system",
        )

    def _fail(self, msg: str) -> ToolResult:
        return ToolResult(tool_name=self.tool_id, content=msg, success=False)

    def execute(self, **params: Any) -> ToolResult:
        if sys.platform != "win32":
            return self._fail("obs_control is Windows only.")
        action = str(params.get("action", "")).strip().lower()
        if action not in _ACTIONS:
            return self._fail(f"Unknown action '{action}'. Allowed: {', '.join(_ACTIONS)}.")

        cfg = _ws_settings()
        if not cfg["enabled"]:
            return self._fail("OBS WebSocket server is disabled. Enable it in OBS: Tools > WebSocket Server Settings.")

        started = False
        if not _port_open(cfg["port"]):
            err = _launch_obs()
            if err:
                return self._fail(err)
            started = True
            if action == "launch":
                return ToolResult(tool_name=self.tool_id, content="OBS is starting (I did not wait for its window).", success=True)
        elif action == "launch":
            return ToolResult(tool_name=self.tool_id, content="OBS was already running.", success=True)

        try:
            cl = _connect(cfg["port"], cfg["password"], wait_s=45 if started else 8)
        except Exception as exc:
            return self._fail(str(exc))
        prefix = "OBS was closed, I opened it. " if started else ""

        try:
            return ToolResult(tool_name=self.tool_id, content=prefix + self._run(cl, action, str(params.get("name", "") or "").strip()), success=True)
        except RuntimeError as exc:
            return self._fail(prefix + str(exc))
        except Exception as exc:
            return self._fail(prefix + f"OBS refused the request: {exc}")

    # -- actions ---------------------------------------------------------
    def _run(self, cl, action: str, name: str) -> str:
        if action == "status":
            return self._status(cl)
        if action == "start_stream":
            if cl.get_stream_status().output_active:
                return "Already live; nothing changed. " + self._status(cl)
            cl.start_stream()
            ok = _wait_until(lambda: cl.get_stream_status().output_active, 12)
            if not ok:
                raise RuntimeError("I asked OBS to start the stream but it is NOT live (check the stream key / service in OBS settings).")
            return "Stream started: OBS reports it is LIVE. " + self._status(cl)
        if action == "stop_stream":
            if not cl.get_stream_status().output_active:
                return "The stream was not live; nothing changed."
            cl.stop_stream()
            if not _wait_until(lambda: not cl.get_stream_status().output_active, 12):
                raise RuntimeError("I asked OBS to stop the stream but it still reports LIVE.")
            return "Stream stopped: OBS reports it is offline."
        if action == "start_record":
            if cl.get_record_status().output_active:
                return "Already recording; nothing changed."
            cl.start_record()
            if not _wait_until(lambda: cl.get_record_status().output_active, 8):
                raise RuntimeError("I asked OBS to record but it is NOT recording.")
            return "Recording started: OBS reports it is recording."
        if action == "stop_record":
            if not cl.get_record_status().output_active:
                return "It was not recording; nothing changed."
            res = cl.stop_record()
            _wait_until(lambda: not cl.get_record_status().output_active, 10)
            return f"Recording stopped. File: {getattr(res, 'output_path', 'unknown')}."
        if action == "list_scenes":
            scenes = [s["sceneName"] for s in cl.get_scene_list().scenes]
            return f"Scenes ({len(scenes)}): " + (", ".join(scenes) or "none")
        if action == "set_scene":
            scenes = [s["sceneName"] for s in cl.get_scene_list().scenes]
            match = next((s for s in scenes if s.lower() == name.lower()), None)
            if not name or match is None:
                raise RuntimeError(f"Scene '{name}' does not exist. Available: {', '.join(scenes)}.")
            cl.set_current_program_scene(match)
            now = cl.get_current_program_scene().current_program_scene_name
            if now != match:
                raise RuntimeError(f"I asked for scene '{match}' but OBS is on '{now}'.")
            return f"Scene is now '{now}'."
        if action in ("mute_mic", "unmute_mic"):
            inputs = [i["inputName"] for i in cl.get_input_list().inputs]
            if name:
                target = next((i for i in inputs if i.lower() == name.lower()), None)
            else:
                target = next((i for i in inputs if any(k in i.lower() for k in ("mic", "micr", "aux", "audio de entrada"))), None)
            if target is None:
                raise RuntimeError(f"Audio input not found. Inputs in OBS: {', '.join(inputs) or 'none'}.")
            want = action == "mute_mic"
            cl.set_input_mute(target, want)
            got = cl.get_input_mute(target).input_muted
            if got != want:
                raise RuntimeError(f"I asked to {'mute' if want else 'unmute'} '{target}' but OBS reports muted={got}.")
            return f"'{target}' is now {'MUTED' if got else 'unmuted'}."
        raise RuntimeError("Unhandled action.")

    @staticmethod
    def _status(cl) -> str:
        stream = cl.get_stream_status()
        rec = cl.get_record_status()
        scene = cl.get_current_program_scene().current_program_scene_name
        parts = [f"scene '{scene}'", "LIVE" if stream.output_active else "not live",
                 "recording" if rec.output_active else "not recording"]
        if stream.output_active:
            parts.append(f"live for {getattr(stream, 'output_timecode', '?')[:8]}")
        return "OBS status: " + ", ".join(parts) + "."
