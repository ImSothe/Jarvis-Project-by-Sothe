"""Catch a model that says it did something without calling the tool.

Small models imitate their own earlier replies: after a few turns of "pausa Spotify" ->
"Spotify pausado" they start answering "Spotify pausado" without calling any tool, and
nothing actually happens. When the user gave a command, the reply claims an action, and
no tool ran in this turn, the agent loop sends the model back once with a nudge to act.

Deliberately narrow (the request must look like a command AND the reply must read like
a completed action) so ordinary answers are never retried; a false positive costs one
extra model call, never a wrong action.
"""

from __future__ import annotations

import re

# Imperative commands in Spanish and English ("pon", "pausa", "abre", "sube"...).
_COMMAND_RE = re.compile(
    r"\b(pon|pone|ponme|ponlo|ponla|pausa|pausar|pausalo|para|parar|reanuda|reanudar|"
    r"continua|continúa|siguiente|anterior|salta|abre|abrir|abreme|cierra|cerrar|sube|"
    r"subir|baja|bajar|silencia|silenciar|mutea|quita|quitar|reproduce|reproducir|"
    r"guarda|guardar|a[ñn]ade|a[ñn]adir|play|pause|resume|next|previous|skip|open|"
    r"close|mute|unmute|stop)\b",
    re.IGNORECASE,
)

# Replies that read like a finished action ("Spotify pausado", "ya lo tienes sonando").
_CLAIM_RE = re.compile(
    r"(pausad[oa]|reanudad[oa]|silenciad[oa]|abiert[oa]|cerrad[oa]|subid[oa]|"
    r"bajad[oa]|guardad[oa]|a[ñn]adid[oa]|sonando|reproduciendo|ya lo tienes|"
    r"ya la tienes|ya te lo|ya est[aá] (puesto|puesta|pausado|abierto)|"
    r"\b(paused|resumed|muted|opened|closed|playing|saved|added)\b)",
    re.IGNORECASE,
)

NO_TOOL_NUDGE = (
    "Aviso del sistema: en este turno no has llamado a ninguna herramienta, así que "
    "NO se ha hecho nada, y tu respuesta anterior dice lo contrario. Si el usuario "
    "pidió una acción (música, volumen, abrir una app...), llama ahora a la "
    "herramienta adecuada. Si no era una orden, vuelve a responder sin afirmar que "
    "has hecho nada. (System notice: you called no tool this turn, so nothing was "
    "done. Call the right tool now, or answer again without claiming any action.)"
)


def claims_unperformed_action(user_text: str, reply: str) -> bool:
    """True when ``user_text`` is a command and ``reply`` claims it was carried out."""
    return bool(_COMMAND_RE.search(user_text or "") and _CLAIM_RE.search(reply or ""))
