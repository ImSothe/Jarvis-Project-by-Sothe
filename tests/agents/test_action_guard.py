"""A reply that claims an action without any tool having run is sent back once."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openjarvis.agents.action_guard import NO_TOOL_NUDGE, claims_unperformed_action
from openjarvis.agents.orchestrator import OrchestratorAgent
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


@pytest.mark.parametrize(
    "user, reply",
    [
        # The real cases from the traces: it copied its own earlier answer.
        ("Jarvis, pausa Spotify.", "Spotify pausado, silencio en cabina."),
        ("Jarvis, pon Quevedo.", "Ya lo tienes sonando, Quevedo al aparato."),
        ("Jarvis, abre Discord", "Te he abierto Discord, a tope."),
        ("sube el volumen", "Volumen subido al 60 por ciento."),
        ("pause the music", "Music paused."),
    ],
)
def test_command_plus_claim_is_flagged(user, reply):
    assert claims_unperformed_action(user, reply)


@pytest.mark.parametrize(
    "user, reply",
    [
        # A question, not a command: even if the answer has a "claim" word.
        (
            "¿Qué casco es mejor?",
            "Te recomiendo el Alpinestars, tiene la visera abierta.",
        ),
        (
            "Jarvis, ¿qué tal el día?",
            "Muy bien, con música sonando de fondo en mi cabeza.",
        ),
        # A command whose answer does not claim anything.
        ("pon Quevedo", "No encuentro ese artista, ¿puedes repetirlo?"),
        ("pausa Spotify", "¿Quieres que lo pause ahora?"),
        ("", ""),
    ],
)
def test_normal_answers_are_not_flagged(user, reply):
    assert not claims_unperformed_action(user, reply)


class _SpotifyStub(BaseTool):
    tool_id = "spotify_control"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="spotify_control",
            description="Control Spotify.",
            parameters={
                "type": "object",
                "properties": {"action": {"type": "string"}},
                "required": ["action"],
            },
        )

    def execute(self, **params) -> ToolResult:
        return ToolResult(tool_name="spotify_control", content="Paused.", success=True)


def _reply(content: str, tool_call: dict | None = None) -> dict:
    out = {
        "content": content,
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        "model": "test-model",
        "finish_reason": "tool_calls" if tool_call else "stop",
    }
    if tool_call:
        out["tool_calls"] = [tool_call]
    return out


_PAUSE_CALL = {"id": "c1", "name": "spotify_control", "arguments": '{"action":"pause"}'}


def _agent(*replies: dict) -> tuple[OrchestratorAgent, MagicMock]:
    engine = MagicMock()
    engine.engine_id = "mock"
    engine.generate.side_effect = list(replies)
    return OrchestratorAgent(engine, "test-model", tools=[_SpotifyStub()]), engine


class TestOrchestratorRetry:
    def test_false_claim_is_retried_and_the_tool_then_runs(self):
        agent, engine = _agent(
            _reply("Spotify pausado, silencio en cabina."),  # claims, no tool
            _reply("", _PAUSE_CALL),  # after the nudge: calls the tool
            _reply("Ahora sí, pausado."),
        )
        result = agent.run("Jarvis, pausa Spotify.")
        assert [r.tool_name for r in result.tool_results] == ["spotify_control"]
        assert result.content == "Ahora sí, pausado."
        # the model was told why it was sent back
        second_call_messages = engine.generate.call_args_list[1].args[0]
        assert NO_TOOL_NUDGE in [m.content for m in second_call_messages]

    def test_only_one_retry(self):
        agent, engine = _agent(
            _reply("Spotify pausado."),
            _reply("Spotify pausado, de verdad."),  # insists: it is returned as is
        )
        result = agent.run("pausa Spotify")
        assert engine.generate.call_count == 2
        assert result.content == "Spotify pausado, de verdad."

    def test_no_retry_when_the_tool_really_ran(self):
        agent, engine = _agent(_reply("", _PAUSE_CALL), _reply("Spotify pausado."))
        result = agent.run("pausa Spotify")
        assert engine.generate.call_count == 2  # tool turn + final answer, no nudge
        assert result.content == "Spotify pausado."

    def test_no_retry_for_a_plain_question(self):
        agent, engine = _agent(_reply("Te recomiendo el Alpinestars, visera abierta."))
        agent.run("¿Qué casco es mejor?")
        assert engine.generate.call_count == 1

    def test_no_retry_when_the_agent_has_no_tools(self):
        engine = MagicMock()
        engine.engine_id = "mock"
        engine.generate.side_effect = [_reply("Spotify pausado.")]
        OrchestratorAgent(engine, "test-model").run("pausa Spotify")
        assert engine.generate.call_count == 1
