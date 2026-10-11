"""Tool routing: send only the tools a request can need."""

from __future__ import annotations

import json

import pytest

from openjarvis.agents import tool_router as tr


def _fake_tools(extra=("custom_future_tool",)):
    names = set(tr.CORE) | tr.tools_for_groups(tr.GROUPS) | set(extra)
    return [
        {"type": "function", "function": {"name": n, "description": "x" * 400, "parameters": {}}}
        for n in sorted(names)
    ]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Jarvis, pon Quevedo", set()),
        ("¿qué tiempo hace mañana?", {"weather", "calendar"}),
        ("sube el volumen al 50", {"pc"}),
        ("mira mi correo", {"mail"}),
        ("analiza este reel de instagram", {"content"}),
        ("cuántos fps gano si optimizo windows", {"optimizer"}),
    ],
)
def test_matched_groups(text, expected):
    assert tr.matched_groups(text) == expected


def test_music_request_sends_few_tools():
    tools = _fake_tools()
    kept = tr.filter_tools(tools, tr.initial_tool_names("pon Quevedo"))
    names = {t["function"]["name"] for t in kept}
    assert {"spotify_play", "open_app", tr.MORE_TOOLS} <= names
    assert "gmail_send_email" not in names
    assert len(json.dumps(kept)) < len(json.dumps(tools)) / 3


def test_unknown_tools_are_never_hidden():
    kept = tr.filter_tools(_fake_tools(), tr.initial_tool_names("hola"))
    assert "custom_future_tool" in {t["function"]["name"] for t in kept}


def test_more_tools_group_names_are_valid():
    enum = tr.more_tools_spec()["function"]["parameters"]["properties"]["groups"]["items"]["enum"]
    assert set(enum) == set(tr.GROUPS)
    assert tr.tools_for_groups(["mail"]) == set(tr.GROUPS["mail"][0])
    assert tr.tools_for_groups(["nope"]) == set()
