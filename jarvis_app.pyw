"""Jarvis as a desktop app: its own window (WebView2), icon and taskbar identity.

Starts the local server if it is not running (hidden), shows a splash meanwhile and loads the UI
when it is ready. Closing the window leaves the server running (autostart/voice keep working).
"""
import ctypes
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
URL = 'http://localhost:5173'
AUMID = 'Sothe.Jarvis'
DATA = Path(os.environ.get('LOCALAPPDATA', str(ROOT))) / 'Jarvis'
DATA.mkdir(parents=True, exist_ok=True)
LOG = DATA / 'app.log'

SPLASH = """<!doctype html><meta charset=utf-8><body style="margin:0;background:#000;height:100vh;display:grid;place-items:center;font-family:Consolas,monospace;color:#00d2ff">
<div style="text-align:center"><div style="width:90px;height:90px;margin:0 auto 22px;border-radius:50%;border:3px solid #00d2ff;box-shadow:0 0 30px #00d2ff;animation:p 1.4s ease-in-out infinite"></div>
<div style="letter-spacing:.3em;font-size:13px">ARRANCANDO JARVIS…</div></div>
<style>@keyframes p{50%{transform:scale(1.15);opacity:.5}}</style></body>"""


def log(msg: str) -> None:
    try:
        with LOG.open('a', encoding='utf-8') as f:
            f.write(f'{time.strftime("%H:%M:%S")} {msg}\n')
    except OSError:
        pass


def port_up(port: int) -> bool:
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.4):
            return True
    except OSError:
        return False


def server_ready() -> bool:
    return port_up(5173) and port_up(8000)


def start_server() -> None:
    if server_ready():
        return  # the full stack is already running
    flags = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP (DETACHED would leave powershell without a console)
    subprocess.Popen(
        ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden',
         '-File', str(ROOT / 'start-jarvis.ps1'), '-NoBrowser'],
        cwd=str(ROOT), creationflags=flags, close_fds=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def focus_existing() -> bool:
    """One instance only: if Jarvis is already open, bring it to the front."""
    hwnd = ctypes.windll.user32.FindWindowW(None, 'Jarvis')
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 9)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        return True
    return False


def prepare_window(window) -> None:
    """Window icon + allow the microphone for the local UI without asking every time."""
    try:
        import clr  # noqa: F401
        from System.Drawing import Icon
        deadline = time.time() + 15
        while time.time() < deadline and getattr(window, 'native', None) is None:
            time.sleep(0.1)
        form = window.native
        form.Icon = Icon(str(ROOT / 'jarvis.ico'))
        log('icon set')
    except Exception:
        log('icon failed: ' + traceback.format_exc())
    try:
        from System import Action
        from Microsoft.Web.WebView2.Core import CoreWebView2PermissionKind, CoreWebView2PermissionState

        def on_permission(_sender, args):
            if args.PermissionKind == CoreWebView2PermissionKind.Microphone and str(args.Uri).startswith(URL):
                args.State = CoreWebView2PermissionState.Allow

        def attach():  # CoreWebView2 may only be touched from the UI thread
            core = window.native.webview.CoreWebView2
            core.PermissionRequested += on_permission
            log('mic permission handler set')

        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                window.native.Invoke(Action(attach))
                break
            except Exception:
                time.sleep(0.3)
        else:
            log('permission handler: CoreWebView2 never became ready')
    except Exception:
        log('permission handler failed: ' + traceback.format_exc())


def boot(window) -> None:
    prepare_window_thread = threading.Thread(target=prepare_window, args=(window,), daemon=True)
    prepare_window_thread.start()
    try:
        start_server()
        deadline = time.time() + 180
        while not server_ready():
            if time.time() > deadline:
                window.load_html('<body style="background:#000;color:#f44;font-family:Consolas;padding:40px">'
                                 'Jarvis no arrancó en 3 min. Abre jarvis-terminal.cmd para ver el error.</body>')
                return
            time.sleep(0.7)
        time.sleep(2)  # let the frontend finish its first compile
        window.load_url(URL)
        log('ui loaded')
        time.sleep(4)
        log('page: ' + str(window.evaluate_js('document.title + " | root=" + (document.getElementById("root")||{children:[]}).children.length')))
    except Exception:
        log('boot failed: ' + traceback.format_exc())


def main() -> None:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(AUMID)
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, r'Local\Sothe.Jarvis.App')
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        focus_existing()
        return
    # WebView2 freezes timers/audio of a covered or minimized window; voice and autostart need it awake.
    os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = (
        '--disable-background-timer-throttling --disable-renderer-backgrounding '
        '--disable-backgrounding-occluded-windows --disable-features=CalculateNativeWinOcclusion')
    import webview
    window = webview.create_window('Jarvis', html=SPLASH, width=1100, height=800, min_size=(700, 500),
                                   background_color='#000000')
    webview.start(boot, window, gui='edgechromium', private_mode=False, storage_path=str(DATA / 'webview'))
    del mutex


if __name__ == '__main__':
    try:
        main()
    except Exception:
        log('fatal: ' + traceback.format_exc())
