"""Product knowledge for Sothe Optimizer (formerly TOJI): read the real data.

Reads the JSON that drives the optimizer (tweaks, profiles, features, apps) from
the project folder at call time, so answers always match the data and nothing is
invented from memory. A curated overview (architecture, rules, honest caveats)
lives in ``~/.openjarvis/knowledge/sothe_optimizer_overview.md``.

Folder: env SOTHE_OPTIMIZER_DIR, default ~/Documents/Proyectos/Sothe-Optimizer
(the PowerShell source in ``fuente-powershell-TOJI``). The compiled C# release is
NOT readable from here, so counts or features may differ from that build.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.core.config import DEFAULT_CONFIG_DIR
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_DEFAULT_DIR = r"~\Documents\Proyectos\Sothe-Optimizer"
_OVERVIEW = DEFAULT_CONFIG_DIR / "knowledge" / "sothe_optimizer_overview.md"
_MAX_RESULTS = 25


def _src() -> Path:
    base = Path(os.environ.get("SOTHE_OPTIMIZER_DIR", _DEFAULT_DIR))
    return base / "fuente-powershell-TOJI"


def _load(name: str) -> Any:
    return json.loads((_src() / name).read_text(encoding="utf-8-sig"))


def _tweaks() -> List[Dict[str, Any]]:
    data = _load("tweaks.json")
    return data["tweaks"] if isinstance(data, dict) else data


def _fmt_op(op: Dict[str, Any]) -> str:
    t = op.get("type")
    if t == "reg":
        return f"[registro] {op.get('path')}\\{op.get('name')} = {op.get('value')} ({op.get('kind', 'DWord')})"
    if t == "service":
        return f"[servicio] {op.get('name')} -> inicio {op.get('startup')}"
    if t == "command":
        rev = op.get("revert") or "(SIN revert definido)"
        return f"[comando] aplica: {op.get('apply')}  | revierte: {rev}"
    if t == "appx":
        return f"[appx] elimina el paquete {op.get('package')} (NO se revierte automaticamente: reinstalar desde Microsoft Store)"
    return f"[{t}] {json.dumps(op, ensure_ascii=False)}"


def _auto_reversible(tw: Dict[str, Any]) -> bool:
    for op in tw.get("ops", []):
        if op.get("type") == "appx" or (op.get("type") == "command" and not op.get("revert")):
            return False
    return True


def _line(tw: Dict[str, Any]) -> str:
    flags = []
    if tw.get("anticheat"):
        flags.append("ANTICHEAT")
    if tw.get("reboot"):
        flags.append("reinicio")
    if not tw.get("portable", True):
        flags.append("no portatil")
    if not _auto_reversible(tw):
        flags.append("NO auto-reversible")
    extra = f" [{', '.join(flags)}]" if flags else ""
    return f"{tw['id']} | {tw.get('category')} | {tw.get('danger')} | {tw.get('name')}{extra}"


def _detail(tw: Dict[str, Any]) -> str:
    lines = [
        f"ID: {tw['id']}", f"NOMBRE: {tw.get('name')}",
        f"CATEGORIA: {tw.get('category')} | PELIGRO: {tw.get('danger')} | "
        f"REINICIO: {'si' if tw.get('reboot') else 'no'} | RIESGO ANTICHEAT: {'si' if tw.get('anticheat') else 'no'} | "
        f"PORTATIL: {'si' if tw.get('portable', True) else 'no (pensado para sobremesa)'}",
        f"QUE HACE: {tw.get('desc')}",
    ]
    if tw.get("warning"):
        lines.append(f"AVISO: {tw['warning']}")
    lines.append(f"AUTO-REVERSIBLE: {'si' if _auto_reversible(tw) else 'NO (ver operaciones)'}")
    lines.append("OPERACIONES:")
    lines += [f"  - {_fmt_op(op)}" for op in tw.get("ops", [])]
    profiles = [p["name"] for p in _load("profiles.json").get("profiles", []) if tw["id"] in p.get("tweaks", [])]
    lines.append(f"INCLUIDO EN PERFILES: {', '.join(profiles) or 'ninguno'}")
    return "\n".join(lines)


def _blob(tw: Dict[str, Any]) -> str:
    return json.dumps(tw, ensure_ascii=False).lower()


@ToolRegistry.register("optimizer_info")
class OptimizerInfoTool(BaseTool):
    tool_id = "optimizer_info"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="optimizer_info",
            description=(
                "Authoritative product knowledge about Sothe's Windows optimizer (Sothe "
                "Optimizer, formerly TOJI): every tweak with its real registry keys, "
                "services, commands, danger level, anti-cheat and reversibility, plus "
                "profiles, Windows features, apps and the product overview. ALWAYS use it "
                "before explaining or promoting what the optimizer does; never answer "
                "from memory. Actions: overview, list, get, search, profile, reversibility, "
                "anticheat, features, apps."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["overview", "list", "get", "search", "profile",
                                 "reversibility", "anticheat", "features", "apps"],
                    },
                    "id": {"type": "string", "description": "Tweak id (get) or profile id (profile)."},
                    "category": {"type": "string", "description": "Filter for list, e.g. Red, GPU, Privacidad."},
                    "danger": {"type": "string", "enum": ["safe", "moderate", "high", "extreme"]},
                    "query": {"type": "string", "description": "Search text: name, description, registry path, service..."},
                },
                "required": ["action"],
            },
            category="knowledge",
        )

    def _ok(self, text: str) -> ToolResult:
        return ToolResult(tool_name=self.tool_id, content=text, success=True)

    def _err(self, text: str) -> ToolResult:
        return ToolResult(tool_name=self.tool_id, content=text, success=False)

    def execute(self, **p: Any) -> ToolResult:
        action = str(p.get("action", "")).strip().lower()
        try:
            if action == "overview":
                try:
                    text = _OVERVIEW.read_text(encoding="utf-8-sig")
                except OSError:
                    text = "(overview file missing)"
                tw = _tweaks()
                by_danger: Dict[str, int] = {}
                for t in tw:
                    by_danger[t["danger"]] = by_danger.get(t["danger"], 0) + 1
                live = (f"\n\nDATOS EN VIVO (tweaks.json): {len(tw)} ajustes | por peligro: {by_danger} | "
                        f"perfiles: {len(_load('profiles.json').get('profiles', []))} | "
                        f"apps: {len(self._apps())} | caracteristicas de Windows: {len(_load('features.json').get('features', []))}")
                return self._ok(text + live)
            if action in ("list", "search", "reversibility", "anticheat"):
                return self._listing(action, p)
            if action == "get":
                wanted = str(p.get("id", "")).strip().lower()
                tw = next((t for t in _tweaks() if t["id"].lower() == wanted), None)
                if not tw:
                    close = [t["id"] for t in _tweaks() if wanted and wanted in t["id"].lower()][:8]
                    return self._err(f"No tweak with id '{wanted}'." + (f" Similar: {', '.join(close)}" if close else ""))
                return self._ok(_detail(tw))
            if action == "profile":
                profiles = _load("profiles.json").get("profiles", [])
                wanted = str(p.get("id", "")).strip().lower()
                if not wanted:
                    return self._ok("\n".join(f"{x['id']} | {x['name']} | {len(x.get('tweaks', []))} ajustes | {x.get('desc')}" for x in profiles))
                prof = next((x for x in profiles if x["id"].lower() == wanted or x["name"].lower() == wanted), None)
                if not prof:
                    return self._err("Unknown profile. Use action=profile without id to list them.")
                by_id = {t["id"]: t for t in _tweaks()}
                rows = [_line(by_id[i]) if i in by_id else f"{i} | (id no encontrado en tweaks.json)" for i in prof.get("tweaks", [])]
                return self._ok(f"{prof['name']}: {prof.get('desc')}\n" + "\n".join(rows) if rows else f"{prof['name']}: {prof.get('desc')}\n(sin ajustes: revierte todo)")
            if action == "features":
                return self._ok("\n".join(f"{f['name']} ({f['feature']}): {f.get('desc')}" for f in _load("features.json").get("features", [])))
            if action == "apps":
                return self._ok("\n".join(f"{a.get('category')} | {a.get('name')}" for a in self._apps()))
        except FileNotFoundError as exc:
            return self._err(f"Optimizer data not found ({exc.filename}). Set SOTHE_OPTIMIZER_DIR.")
        except (ValueError, KeyError) as exc:
            return self._err(f"Could not read optimizer data: {exc}")
        return self._err("Unknown action.")

    @staticmethod
    def _apps() -> List[Dict[str, Any]]:
        data = _load("apps.json")
        return data["apps"] if isinstance(data, dict) else data

    def _listing(self, action: str, p: Dict[str, Any]) -> ToolResult:
        rows = _tweaks()
        if action == "reversibility":
            rows = [t for t in rows if not _auto_reversible(t)]
            head = f"{len(rows)} ajustes NO totalmente auto-reversibles (eliminan apps o tienen comandos sin revert):\n"
        elif action == "anticheat":
            rows = [t for t in rows if t.get("anticheat")]
            head = "Ajustes marcados con riesgo anti-cheat en los datos:\n"
        else:
            head = ""
            if p.get("category"):
                rows = [t for t in rows if str(t.get("category", "")).lower() == str(p["category"]).lower()]
            if p.get("danger"):
                rows = [t for t in rows if t.get("danger") == p["danger"]]
            if action == "search":
                q = str(p.get("query", "")).strip().lower()
                if not q:
                    return self._err("A query is required.")
                rows = [t for t in rows if q in _blob(t)]
        shown = rows[:_MAX_RESULTS]
        more = f"\n(+{len(rows) - len(shown)} mas; afina el filtro)" if len(rows) > len(shown) else ""
        return self._ok(head + ("\n".join(_line(t) for t in shown) or "Sin resultados.") + more)
