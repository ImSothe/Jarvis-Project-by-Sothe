"""General PC control for Jarvis (Windows): volume, lock, power, screenshot, status, close apps.

Everything is a fixed action with fixed commands: no shell strings, no paths or
commands from the model. Closing apps only works for programs in the user's
``apps.json`` allowlist and sends a normal close request (the app may ask to
save). Sleep, shutdown and restart need ``confirm=true`` and shutdown/restart
start a 60 s countdown that ``cancel_shutdown`` can abort.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec
from openjarvis.tools.open_app import _load_apps, _resolve

_ACTIONS = (
    "get_volume", "set_volume", "mute", "unmute", "lock", "show_desktop", "screenshot",
    "system_status", "running_apps", "close_app",
    "sleep", "shutdown", "restart", "cancel_shutdown",
)
_NEEDS_CONFIRM = ("sleep", "shutdown", "restart")
_NEVER_CLOSE = {"explorer.exe", "csrss.exe", "winlogon.exe", "svchost.exe", "system"}
_NO_WINDOW = 0x08000000


def _endpoint():
    from pycaw.pycaw import AudioUtilities

    return AudioUtilities.GetSpeakers().EndpointVolume


def _run(argv: list, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        argv, shell=False, capture_output=True, text=True, timeout=timeout, creationflags=_NO_WINDOW,
    )


def _exe_name(entry: dict) -> str:
    return Path(str(entry.get("path", ""))).name.lower()


@ToolRegistry.register("pc_control")
class PcControlTool(BaseTool):
    tool_id = "pc_control"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="pc_control",
            description=(
                "Control Sothe's PC. Actions: get_volume, set_volume (needs 'level' 0-100), mute, "
                "unmute, lock (lock the PC), show_desktop (minimize everything), screenshot (saves "
                "a PNG in Pictures/Jarvis and returns the path), system_status (CPU, RAM, disk, GPU, "
                "uptime, heaviest programs), running_apps (which approved apps are open), "
                "close_app (needs 'app', an approved app name; asks it to close normally), "
                "sleep / shutdown / restart (ONLY if Sothe explicitly asked this turn, and then pass "
                "confirm=true; shutdown and restart wait 60 s), cancel_shutdown (abort that "
                "countdown). Report exactly what the result says."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": list(_ACTIONS)},
                    "level": {"type": "integer", "description": "Volume 0-100 for set_volume."},
                    "app": {"type": "string", "description": "Approved app name for close_app."},
                    "confirm": {"type": "boolean", "description": "true only after Sothe explicitly asked for sleep/shutdown/restart."},
                },
                "required": ["action"],
            },
            category="system",
            # screenshot's own PowerShell subprocess already budgets 30s; give the executor
            # room beyond that instead of both timeouts racing each other.
            timeout_seconds=45.0,
        )

    def _ok(self, msg: str) -> ToolResult:
        return ToolResult(tool_name=self.tool_id, content=msg, success=True)

    def _fail(self, msg: str) -> ToolResult:
        return ToolResult(tool_name=self.tool_id, content=msg, success=False)

    def execute(self, **params: Any) -> ToolResult:
        if sys.platform != "win32":
            return self._fail("pc_control is Windows only.")
        action = str(params.get("action", "")).strip().lower()
        if action not in _ACTIONS:
            return self._fail(f"Unknown action '{action}'. Allowed: {', '.join(_ACTIONS)}.")
        if action in _NEEDS_CONFIRM and params.get("confirm") is not True:
            return self._fail(f"'{action}' needs explicit confirmation from Sothe. Ask him first, then call again with confirm=true.")
        try:
            return getattr(self, f"_do_{action}")(params)
        except Exception as exc:
            return self._fail(f"{action} failed: {exc}")

    # -- sound -----------------------------------------------------------
    def _do_get_volume(self, _p) -> ToolResult:
        ep = _endpoint()
        return self._ok(f"Volume is {round(ep.GetMasterVolumeLevelScalar() * 100)}%, {'muted' if ep.GetMute() else 'not muted'}.")

    def _do_set_volume(self, p) -> ToolResult:
        try:
            level = int(p.get("level"))
        except (TypeError, ValueError):
            return self._fail("set_volume needs 'level' as a number 0-100.")
        level = max(0, min(100, level))
        ep = _endpoint()
        ep.SetMasterVolumeLevelScalar(level / 100, None)
        now = round(ep.GetMasterVolumeLevelScalar() * 100)
        return self._ok(f"Volume set; Windows reports {now}%.")

    def _do_mute(self, _p) -> ToolResult:
        ep = _endpoint(); ep.SetMute(1, None)
        return self._ok(f"Windows reports muted={bool(ep.GetMute())}.")

    def _do_unmute(self, _p) -> ToolResult:
        ep = _endpoint(); ep.SetMute(0, None)
        return self._ok(f"Windows reports muted={bool(ep.GetMute())}.")

    # -- session ---------------------------------------------------------
    def _do_lock(self, _p) -> ToolResult:
        if not ctypes.windll.user32.LockWorkStation():  # type: ignore[attr-defined]
            return self._fail("Windows refused to lock the PC.")
        return self._ok("PC locked.")

    def _do_show_desktop(self, _p) -> ToolResult:
        u = ctypes.windll.user32  # type: ignore[attr-defined]
        for vk, up in ((0x5B, False), (0x44, False), (0x44, True), (0x5B, True)):  # Win+D
            u.keybd_event(vk, 0, 2 if up else 0, 0)
        return self._ok("Sent Win+D (show desktop). I cannot see the screen to confirm.")

    def _do_screenshot(self, _p) -> ToolResult:
        folder = Path.home() / "Pictures" / "Jarvis"
        folder.mkdir(parents=True, exist_ok=True)
        out = folder / time.strftime("screenshot-%Y%m%d-%H%M%S.png")
        script = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
            "$b=[System.Windows.Forms.SystemInformation]::VirtualScreen;"
            "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
            "$g=[System.Drawing.Graphics]::FromImage($bmp);"
            "$g.CopyFromScreen($b.Left,$b.Top,0,0,$bmp.Size);"
            f"$bmp.Save('{out}')"
        )
        _run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], timeout=30)
        if not out.exists():
            return self._fail("The screenshot file was not created.")
        return self._ok(f"Screenshot saved to {out} ({out.stat().st_size // 1024} KB). I have not looked at it.")

    # -- information -----------------------------------------------------
    def _do_system_status(self, _p) -> ToolResult:
        import psutil

        cpu = psutil.cpu_percent(interval=0.6)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        up_h = (time.time() - psutil.boot_time()) / 3600
        procs = {}
        for pr in psutil.process_iter(["name", "memory_info"]):
            try:
                procs[pr.info["name"]] = procs.get(pr.info["name"], 0) + pr.info["memory_info"].rss
            except (psutil.Error, TypeError):
                continue
        top = sorted(procs.items(), key=lambda kv: kv[1], reverse=True)[:5]
        gpu = ""
        try:
            r = _run(["nvidia-smi", "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total",
                      "--format=csv,noheader,nounits"], timeout=8)
            if r.returncode == 0 and r.stdout.strip():
                n, util, temp, used, total = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
                gpu = f" GPU {n}: {util}% use, {temp}C, {used}/{total} MB VRAM."
        except Exception:
            pass
        return self._ok(
            f"CPU {cpu:.0f}%. RAM {mem.percent:.0f}% ({mem.used / 2**30:.1f}/{mem.total / 2**30:.1f} GB). "
            f"Disk C: {disk.percent:.0f}% ({disk.free / 2**30:.0f} GB free).{gpu} Uptime {up_h:.1f} h. "
            "Heaviest by RAM: " + ", ".join(f"{n} {b / 2**20:.0f} MB" for n, b in top) + "."
        )

    def _running_exes(self) -> set:
        import psutil

        names = set()
        for pr in psutil.process_iter(["name"]):
            try:
                names.add(str(pr.info["name"]).lower())
            except psutil.Error:
                continue
        return names

    def _do_running_apps(self, _p) -> ToolResult:
        running = self._running_exes()
        apps = _load_apps()
        openn = sorted(k for k, e in apps.items() if _exe_name(e) and _exe_name(e) in running and _exe_name(e) not in _NEVER_CLOSE)
        return self._ok("Approved apps currently running: " + (", ".join(openn) or "none") + ". (Games opened through Steam/Epic are not tracked.)")

    def _do_close_app(self, p) -> ToolResult:
        apps = _load_apps()
        key = _resolve(apps, str(p.get("app", ""))) if p.get("app") else None
        if key is None:
            return self._fail(f"'{p.get('app', '')}' is not on the approved list: {', '.join(sorted(apps))}.")
        exe = _exe_name(apps[key])
        if not exe or exe in _NEVER_CLOSE:
            return self._fail(f"'{key}' cannot be closed with this tool.")
        if exe not in self._running_exes():
            return self._ok(f"{key} was not running.")
        _run(["taskkill", "/IM", exe])   # no /F: a normal close request, the app can ask to save
        time.sleep(2)
        still = exe in self._running_exes()
        return self._ok(f"Asked {key} to close; it is {'STILL running (it may be asking to save or be minimized to the tray)' if still else 'closed'}.")

    # -- power -----------------------------------------------------------
    def _do_sleep(self, _p) -> ToolResult:
        _run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], timeout=5)
        return self._ok("Sleep requested.")

    def _do_shutdown(self, _p) -> ToolResult:
        r = _run(["shutdown", "/s", "/t", "60"])
        return self._ok("Shutdown scheduled in 60 s. Say 'cancela' to abort.") if r.returncode == 0 else self._fail(r.stderr.strip() or "shutdown failed")

    def _do_restart(self, _p) -> ToolResult:
        r = _run(["shutdown", "/r", "/t", "60"])
        return self._ok("Restart scheduled in 60 s. Say 'cancela' to abort.") if r.returncode == 0 else self._fail(r.stderr.strip() or "restart failed")

    def _do_cancel_shutdown(self, _p) -> ToolResult:
        r = _run(["shutdown", "/a"])
        return self._ok("Pending shutdown/restart cancelled.") if r.returncode == 0 else self._fail("There was no shutdown or restart pending.")
