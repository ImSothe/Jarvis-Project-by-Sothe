"""Send the model only the tools a request can plausibly need.

Every tool definition is sent on every request, and ~65 of them weigh ~12k tokens, which is
nearly the whole cost of a short request like "pon Quevedo". A small core is always sent; the
rest is picked by keywords in the user's message. If the model still needs something else it can
call ``more_tools`` to load a whole group, so a wrong guess costs one extra turn, not a failure.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Set

MORE_TOOLS = "more_tools"
# Agents with only a handful of tools get all of them; routing only pays off with a big set.
MIN_TOOLS_TO_ROUTE = 12

# Always sent: the tools used for most requests.
CORE = (
    "spotify_play", "spotify_control", "open_app", "media_control",
    "web_search", "calculator", "think",
)

# group -> (tools, keyword stems matched at the start of a word, accent-insensitive)
GROUPS: Dict[str, tuple] = {
    "pc": (
        ("pc_control", "obs_control", "install_app", "shell_exec"),
        ("volumen", "brillo", "apag", "reinici", "bloque", "captur", "pantall", "obs", "grab",
         "stream", "instal", "descarg", "terminal", "comando", "ventana", "minimiz", "ordenador",
         "pc", "wifi", "bluetooth", "bateria", "proceso", "cierr", "cerrar", "camara", "monitor"),
    ),
    "calendar": (
        ("calendar_get_events_today", "calendar_search_events", "calendar_next_meeting",
         "calendar_create_event", "calendar_upcoming", "calendar_search"),
        ("calendari", "agenda", "reunion", "cita", "evento", "hoy", "manana", "semana", "proxim",
         "recordatorio", "recuerdame", "quedada", "libre", "ocupado"),
    ),
    "mail": (
        ("gmail_search_emails", "gmail_list_unread", "gmail_get_thread", "gmail_send_email"),
        ("correo", "mail", "gmail", "bandeja", "inbox", "email"),
    ),
    "content": (
        ("instagram_account_overview", "instagram_recent_posts", "instagram_post_insights",
         "x_analytics", "content_memory", "find_viral_videos", "analyze_video"),
        ("instagram", "insta", "reel", "tiktok", "twitter", "viral", "video", "contenido", "guion",
         "idea", "publicaci", "seguidor", "metrica", "analiz", "youtube", "short", "post", "hook"),
    ),
    "optimizer": (
        ("optimizer_info", "scan_chunks", "knowledge_sql", "digest_collect"),
        ("optimiz", "fps", "rendimiento", "sothe", "resumen", "digest", "conocimiento", "toji",
         "tweak", "lag"),
    ),
    "weather": (
        ("get_weather",),
        ("tiempo", "clima", "llov", "lluvia", "temperatura", "calor", "frio", "pronostic",
         "nublado", "sol", "viento"),
    ),
    "web": (
        ("check_site_trust", "http_request"),
        ("web", "pagina", "sitio", "fiable", "estafa", "comprar", "tienda", "url", "http", "enlace",
         "link", "trust", "segur"),
    ),
    "memory": (
        ("retrieval", "memory_manage", "user_profile_manage", "memory_store", "memory_retrieve",
         "memory_search", "memory_index", "kg_add_entity", "kg_add_relation", "kg_query",
         "kg_neighbors"),
        ("recuerd", "memoria", "acuerd", "olvid", "perfil", "guarda", "apunta", "sabes", "conoces",
         "memoriza"),
    ),
    "files_code": (
        ("file_read", "file_write", "apply_patch", "git_status", "git_diff", "git_commit",
         "git_log", "repl", "code_interpreter", "code_interpreter_docker", "docker_shell_exec",
         "db_query", "skill_manage", "llm"),
        ("archivo", "fichero", "carpeta", "codigo", "script", "git", "commit", "python", "program",
         "sql", "skill", "docker", "repo", "escrib", "lee"),
    ),
    "media_misc": (
        ("image_generate", "pdf_extract", "audio_transcribe", "text_to_speech"),
        ("imagen", "genera", "dibuj", "foto", "pdf", "audio", "transcrib", "voz"),
    ),
    "channels": (
        ("channel_send", "channel_list", "channel_status"),
        ("whatsapp", "telegram", "discord", "slack", "canal", "mandale", "envia", "manda"),
    ),
}

_DESCRIPTION = (
    "Load extra tools when none of the tools you have can do what was asked. Groups: "
    "pc (volume, brightness, OBS, install apps, shell), calendar, mail, "
    "content (Instagram, X, viral videos, scripts/ideas), optimizer, weather, "
    "web (site trust, http), memory, files_code (files, git, python, SQL), "
    "media_misc (images, pdf, audio), channels (WhatsApp/Telegram/Discord/Slack messages)."
)


def more_tools_spec() -> Dict[str, Any]:
    """The meta-tool, in OpenAI function format."""
    return {
        "type": "function",
        "function": {
            "name": MORE_TOOLS,
            "description": _DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": {
                    "groups": {
                        "type": "array",
                        "items": {"type": "string", "enum": sorted(GROUPS)},
                        "description": "Groups to load.",
                    }
                },
                "required": ["groups"],
            },
        },
    }


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def matched_groups(text: str) -> Set[str]:
    """Groups whose keywords appear (as word starts) in ``text``."""
    words = re.findall(r"[a-z0-9]+", _normalize(text))
    found: Set[str] = set()
    for group, (_, stems) in GROUPS.items():
        if any(word.startswith(stem) for word in words for stem in stems):
            found.add(group)
    return found


def tools_for_groups(groups: Iterable[str]) -> Set[str]:
    names: Set[str] = set()
    for group in groups:
        if group in GROUPS:
            names.update(GROUPS[group][0])
    return names


def initial_tool_names(text: str) -> Set[str]:
    """Core tools plus those of every group the text mentions."""
    return set(CORE) | tools_for_groups(matched_groups(text))


def filter_tools(openai_tools: List[Dict[str, Any]], active: Set[str]) -> List[Dict[str, Any]]:
    """Keep the active tools of ``openai_tools`` and add the ``more_tools`` meta-tool.

    Tools not belonging to any group (custom or future ones) are always kept, so adding a tool
    never makes it unreachable.
    """
    grouped = set(CORE).union(*(set(tools) for tools, _ in GROUPS.values()))
    kept = [
        t for t in openai_tools
        if t["function"]["name"] in active or t["function"]["name"] not in grouped
    ]
    kept.append(more_tools_spec())
    return kept
