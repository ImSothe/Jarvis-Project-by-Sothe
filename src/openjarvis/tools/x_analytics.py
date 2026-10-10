"""Analyze Sothe's X (Twitter) posts from files he exports himself - no X API, no cost.

The X API has no free tier for new developers, so this tool reads what X lets him
download for free and drops into ``~/.openjarvis/x_exports/``:

* the analytics CSV (``tweet_activity_metrics_*.csv``: impressions, engagements,
  likes, replies, clicks...), and
* the data archive (Settings > Your account > Download an archive of your data):
  ``tweets.js`` with likes and retweets per post (no impressions).

Read-only: it never touches the network, never posts, and only opens files that
sit directly inside that folder. Numbers are computed here in code so the model
never has to count.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.core.config import DEFAULT_CONFIG_DIR
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

EXPORT_DIR = DEFAULT_CONFIG_DIR / "x_exports"
_MAX_BYTES = 60 * 1024 * 1024
_EXTS = (".csv", ".js", ".json")
_METRICS = ("impressions", "engagements", "likes", "retweets", "replies", "engagement_rate", "url_clicks", "profile_clicks")

# Header names X has used (English UI), normalized to our metric keys.
_COLUMN_MAP = {
    "tweet id": "id", "post id": "id", "id": "id",
    "tweet permalink": "url", "post permalink": "url", "permalink": "url",
    "tweet text": "text", "post text": "text", "text": "text", "full_text": "text",
    "time": "time", "date": "time", "created_at": "time",
    "impressions": "impressions", "engagements": "engagements",
    "engagement rate": "engagement_rate",
    "retweets": "retweets", "reposts": "retweets", "retweet_count": "retweets",
    "replies": "replies", "reply_count": "replies",
    "likes": "likes", "favorite_count": "likes",
    "url clicks": "url_clicks", "user profile clicks": "profile_clicks", "profile visits": "profile_clicks",
}


def _num(value: Any) -> float:
    s = str(value or "").strip().replace("%", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _safe_file(name: str, folder: Path) -> Optional[Path]:
    """Only a bare file name inside the exports folder; no paths, no traversal."""
    if not name or name != Path(name).name or Path(name).suffix.lower() not in _EXTS:
        return None
    path = (folder / name).resolve()
    if path.parent != folder.resolve() or not path.is_file() or path.stat().st_size > _MAX_BYTES:
        return None
    return path


def _read_csv(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        mapping = {h: _COLUMN_MAP.get(re.sub(r"\s+", " ", h.strip().lower())) for h in (reader.fieldnames or [])}
        if "impressions" not in mapping.values() and "likes" not in mapping.values():
            raise ValueError("This CSV has no post metrics columns (impressions / likes).")
        rows = []
        for raw in reader:
            row: Dict[str, Any] = {}
            for h, v in raw.items():
                key = mapping.get(h)
                if key in ("id", "url", "text", "time"):
                    row[key] = str(v or "").strip()
                elif key:
                    row[key] = _num(v)
            if row.get("text") or row.get("id"):
                rows.append(row)
        return rows


def _read_archive(path: Path) -> List[Dict[str, Any]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    start = raw.find("[")
    if start < 0:
        raise ValueError("Not a tweets.js archive file.")
    items = json.loads(raw[start:])
    rows = []
    for item in items:
        t = item.get("tweet", item)
        text = str(t.get("full_text") or t.get("text") or "")
        if text.startswith("RT @"):
            continue  # not his own content
        rows.append({
            "id": str(t.get("id_str") or t.get("id") or ""), "text": text, "time": str(t.get("created_at", "")),
            "likes": _num(t.get("favorite_count")), "retweets": _num(t.get("retweet_count")),
            "url": f"https://x.com/i/status/{t.get('id_str') or t.get('id')}",
        })
    return rows


def load_posts(name: str, folder: Path = EXPORT_DIR) -> List[Dict[str, Any]]:
    path = _safe_file(name, folder)
    if path is None:
        raise FileNotFoundError(f"'{name}' is not a .csv/.js/.json file inside {folder}.")
    return _read_csv(path) if path.suffix.lower() == ".csv" else _read_archive(path)


def summarize(rows: List[Dict[str, Any]]) -> str:
    n = len(rows)
    have = [m for m in _METRICS if any(m in r for r in rows)]
    parts = [f"EXACT TOTAL: {n} posts."]
    for m in have:
        vals = [r.get(m, 0.0) for r in rows]
        if m == "engagement_rate":
            parts.append(f"average engagement rate {sum(vals) / n:.2f}%")
        else:
            parts.append(f"{m}: total {sum(vals):.0f}, average {sum(vals) / n:.1f}, median {sorted(vals)[n // 2]:.0f}")
    return "; ".join(parts) + "."


def top_posts(rows: List[Dict[str, Any]], metric: str, k: int) -> str:
    ranked = sorted(rows, key=lambda r: r.get(metric, 0.0), reverse=True)[:k]
    lines = []
    for i, r in enumerate(ranked, 1):
        text = re.sub(r"\s+", " ", r.get("text", ""))[:110]
        extras = ", ".join(f"{m} {r[m]:.0f}" for m in ("impressions", "likes", "retweets", "replies") if m in r and m != metric)
        lines.append(f"{i}. {metric} {r.get(metric, 0):.0f} ({extras}) [{r.get('time', '')[:16]}] \"{text}\"")
    return "\n".join(lines)


@ToolRegistry.register("x_analytics")
class XAnalyticsTool(BaseTool):
    tool_id = "x_analytics"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="x_analytics",
            description=(
                "Analyze Sothe's X (Twitter) posts from files he exported (no X API; it is paid). "
                "Actions: list_files (what is in his x_exports folder), summary (totals/averages of a "
                "file), top_posts (best posts by a metric: impressions, engagements, likes, retweets, "
                "replies, engagement_rate, url_clicks, profile_clicks). 'file' is a file name from "
                "list_files. The CSV from X analytics has impressions; the data archive only has likes "
                "and retweets. Numbers are exact; never recount or invent. If there are no files, tell "
                "him how to export: analytics CSV (X analytics > Posts > Export) or Settings > Your "
                "account > Download an archive of your data, then drop the file in the folder."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list_files", "summary", "top_posts"]},
                    "file": {"type": "string", "description": "File name from list_files."},
                    "metric": {"type": "string", "enum": list(_METRICS)},
                    "limit": {"type": "integer", "description": "How many posts for top_posts (1-15, default 5)."},
                },
                "required": ["action"],
            },
            category="social",
        )

    def _ok(self, msg: str) -> ToolResult:
        return ToolResult(tool_name=self.tool_id, content=msg, success=True)

    def _fail(self, msg: str) -> ToolResult:
        return ToolResult(tool_name=self.tool_id, content=msg, success=False)

    def execute(self, **params: Any) -> ToolResult:
        folder = EXPORT_DIR
        action = str(params.get("action", "")).strip().lower()
        folder.mkdir(parents=True, exist_ok=True)
        if action == "list_files":
            files = sorted(p.name for p in folder.iterdir() if p.is_file() and p.suffix.lower() in _EXTS)
            if not files:
                return self._ok(f"No X export files yet. Folder: {folder}. He must drop the CSV or tweets.js there.")
            return self._ok(f"Files in {folder}: " + ", ".join(files))
        if action not in ("summary", "top_posts"):
            return self._fail("Unknown action. Use list_files, summary or top_posts.")
        name = str(params.get("file", "") or "").strip()
        if not name:
            files = [p.name for p in folder.iterdir() if p.is_file() and p.suffix.lower() in _EXTS]
            if len(files) != 1:
                return self._fail("Say which 'file' (use list_files first).")
            name = files[0]
        try:
            rows = load_posts(name, folder)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return self._fail(f"Could not read '{name}': {exc}")
        if not rows:
            return self._ok(f"'{name}' has no posts.")
        if action == "summary":
            return self._ok(f"{name}: " + summarize(rows))
        metric = str(params.get("metric", "") or "").strip() or ("impressions" if any("impressions" in r for r in rows) else "likes")
        if metric not in _METRICS or not any(metric in r for r in rows):
            have = [m for m in _METRICS if any(m in r for r in rows)]
            return self._fail(f"This file has no '{metric}'. Available: {', '.join(have)}.")
        try:
            k = max(1, min(int(params.get("limit", 5) or 5), 15))
        except (TypeError, ValueError):
            k = 5
        return self._ok(f"{name} - top {min(k, len(rows))} by {metric} (of {len(rows)} posts):\n" + top_posts(rows, metric, k))
