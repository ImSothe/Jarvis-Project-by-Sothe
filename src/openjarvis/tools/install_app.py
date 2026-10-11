"""Install programs on Sothe's PC through winget (Windows), with guard rails.

Three fixed actions:
  search  - look a program up in the winget community catalog and list candidates
            (name, exact package id, version) so the user can pick the right one;
  install - install ONE package by its exact id, only after the user said yes
            (confirm=true) and only if that id came out of a search in this session;
  check   - ask winget whether a package id is installed now.

Nothing the model writes is ever interpreted by a shell: the id is validated
against a strict pattern and passed as a separate argv item. Installs run in the
background (they can take minutes) and Windows may show its own admin (UAC)
prompt, which only the user can accept.
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from openjarvis.core.config import DEFAULT_CONFIG_DIR
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{1,100}$")
_QUERY_RE = re.compile(r"[^\w\s.+\-]", re.UNICODE)
_NO_WINDOW = 0x08000000
_SEARCHED_TTL_S = 15 * 60
_LOG_DIR = DEFAULT_CONFIG_DIR / "installs"

# id -> time it appeared in a search; install only accepts ids seen recently.
_seen: Dict[str, float] = {}


def _winget(args: List[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["winget", *args, "--accept-source-agreements", "--disable-interactivity"],
        shell=False, capture_output=True, timeout=timeout, creationflags=_NO_WINDOW,
    )


def _text(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def _parse_table(out: str) -> List[Dict[str, str]]:
    """Parse winget's fixed-width table without relying on the UI language."""
    lines = [ln.rstrip("\r") for ln in out.splitlines()]
    sep = next((i for i, ln in enumerate(lines) if re.fullmatch(r"-{10,}", ln.strip())), None)
    if sep is None or sep == 0:
        return []
    header = lines[sep - 1]
    starts = [m.start() for m in re.finditer(r"\S+(?: \S+)*", header)]
    if len(starts) < 3:
        return []
    rows = []
    for ln in lines[sep + 1:]:
        if not ln.strip():
            continue
        cells = [ln[a:b].strip() for a, b in zip(starts, starts[1:] + [len(ln) + 1])]
        if len(cells) >= 3 and _ID_RE.match(cells[1] or ""):
            rows.append({"name": cells[0], "id": cells[1], "version": cells[2]})
    return rows


@ToolRegistry.register("install_app")
class InstallAppTool(BaseTool):
    tool_id = "install_app"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="install_app",
            description=(
                "Install a program on Sothe's PC with winget. Flow: 1) action='search' with "
                "'query' (the program's name) and show him the best match (name + exact id). "
                "2) After he says yes, action='install' with that exact 'id' and confirm=true "
                "(never install without his explicit yes, never an id that did not come from the "
                "search). 3) action='check' with the 'id' to see whether it finished: installs "
                "run in the background and Windows may ask him to accept an admin prompt. If "
                "there is no clear match, say so; do not guess an id."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["search", "install", "check"]},
                    "query": {"type": "string", "description": "Program name for search."},
                    "id": {"type": "string", "description": "Exact winget package id for install/check."},
                    "confirm": {"type": "boolean", "description": "true only after Sothe explicitly agreed to install."},
                },
                "required": ["action"],
            },
            category="system",
            # winget's own search/list subprocess call can take up to 60s (slow connection,
            # first-run source sync); give the executor room for that instead of racing it.
            timeout_seconds=75.0,
        )

    def _ok(self, msg: str, **meta: Any) -> ToolResult:
        return ToolResult(tool_name=self.tool_id, content=msg, success=True, metadata=meta)

    def _fail(self, msg: str) -> ToolResult:
        return ToolResult(tool_name=self.tool_id, content=msg, success=False)

    def execute(self, **params: Any) -> ToolResult:
        if sys.platform != "win32":
            return self._fail("install_app is Windows only.")
        action = str(params.get("action", "")).strip().lower()
        try:
            if action == "search":
                return self._search(str(params.get("query", "") or ""))
            if action == "install":
                return self._install(str(params.get("id", "") or "").strip(), params.get("confirm") is True)
            if action == "check":
                return self._check(str(params.get("id", "") or "").strip())
        except FileNotFoundError:
            return self._fail("winget is not available on this PC (install 'App Installer' from the Microsoft Store).")
        except subprocess.TimeoutExpired:
            return self._fail("winget took too long to answer.")
        return self._fail("Unknown action. Use search, install or check.")

    def _search(self, query: str) -> ToolResult:
        q = re.sub(r"\s+", " ", _QUERY_RE.sub(" ", query)).strip()[:60]
        if len(q) < 2:
            return self._fail("search needs a program name in 'query'.")
        r = _winget(["search", q, "--source", "winget", "--count", "8"])
        rows = _parse_table(_text(r.stdout))
        if not rows:
            return self._ok(f"No package named '{q}' in the winget catalog. Do not guess an id; tell Sothe it was not found.")
        now = time.time()
        for row in rows:
            _seen[row["id"].lower()] = now
        listing = "; ".join(f"{x['name']} [id {x['id']}] v{x['version']}" for x in rows[:6])
        return self._ok(
            f"Matches for '{q}': {listing}. The first one is the closest, but check the name with Sothe "
            "before installing (beware of look-alike names).",
            ids=[x["id"] for x in rows],
        )

    def _install(self, pkg: str, confirm: bool) -> ToolResult:
        if not _ID_RE.match(pkg):
            return self._fail("install needs the exact package id from a search.")
        if not confirm:
            return self._fail("Sothe has not confirmed. Ask him 'quieres que instale X?' and call again with confirm=true after his yes.")
        if time.time() - _seen.get(pkg.lower(), 0) > _SEARCHED_TTL_S:
            return self._fail(f"'{pkg}' did not appear in a recent search. Run search first and use an id from its results.")
        already = _parse_table(_text(_winget(["list", "--id", pkg, "--exact"]).stdout))
        if already:
            return self._ok(f"{pkg} is ALREADY installed (version {already[0]['version']}); I did not touch it.")
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        log = _LOG_DIR / (re.sub(r"[^A-Za-z0-9._-]", "_", pkg) + ".log")
        with open(log, "wb") as fh:
            subprocess.Popen(  # noqa: S603 - validated id as its own argv item, no shell
                ["winget", "install", "--id", pkg, "--exact", "--source", "winget", "--silent",
                 "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity"],
                shell=False, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                creationflags=_NO_WINDOW, close_fds=True,
            )
        return self._ok(
            f"Installation of {pkg} STARTED in the background; it is not finished yet. It can take a few "
            "minutes and Windows may ask Sothe to accept an admin prompt. Use check later to confirm.",
            log=str(log),
        )

    def _check(self, pkg: str) -> ToolResult:
        if not _ID_RE.match(pkg):
            return self._fail("check needs the exact package id.")
        r = _winget(["list", "--id", pkg, "--exact"])
        rows = _parse_table(_text(r.stdout))
        if rows:
            return self._ok(f"{pkg} IS installed (version {rows[0]['version']}).")
        log = _LOG_DIR / (re.sub(r"[^A-Za-z0-9._-]", "_", pkg) + ".log")
        tail = ""
        if log.exists():
            lines = [x.strip() for x in log.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip()]
            tail = " Last installer message: " + (lines[-1][:160] if lines else "(none yet)")
        return self._ok(f"{pkg} is NOT installed yet (still running, waiting for the admin prompt, or it failed).{tail}")
