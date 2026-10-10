"""Control whatever is playing (Spotify, YouTube...) with the Windows media keys.

Fixed allowlist of actions mapped to the standard media virtual-key codes. The
model only picks an action name; nothing else is sent to the system. Windows
only. It does not know what is playing, and play/pause is a toggle.
"""

from __future__ import annotations

import sys
import time
from typing import Any

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_VK = {
    "play_pause": 0xB3,
    "next": 0xB0,
    "previous": 0xB1,
    "stop": 0xB2,
    "volume_up": 0xAF,
    "volume_down": 0xAE,
    "mute": 0xAD,
}
_KEYEVENTF_KEYUP = 0x0002
_MAX_REPEAT = 10  # volume steps are 2% each


def _press(vk: int) -> None:
    import ctypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)


@ToolRegistry.register("media_control")
class MediaControlTool(BaseTool):
    tool_id = "media_control"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="media_control",
            description=(
                "Control the music or video that is playing on Sothe's PC (Spotify, YouTube, "
                "etc.) with the media keys: play_pause (a toggle: if nothing is playing it "
                "resumes the last queue), next, previous, stop, volume_up, volume_down, mute. "
                "It cannot pick a song or know what is playing; to find music, open Spotify "
                "with open_app first."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": list(_VK)},
                    "times": {
                        "type": "integer",
                        "description": f"Repeat count (1-{_MAX_REPEAT}), mainly for volume.",
                    },
                },
                "required": ["action"],
            },
            category="system",
        )

    def execute(self, **params: Any) -> ToolResult:
        if sys.platform != "win32":
            return ToolResult(tool_name=self.tool_id, content="media_control is Windows only.", success=False)
        action = str(params.get("action", "")).strip().lower()
        vk = _VK.get(action)
        if vk is None:
            return ToolResult(
                tool_name=self.tool_id,
                content=f"Unknown action '{action}'. Allowed: {', '.join(_VK)}.",
                success=False,
            )
        try:
            times = max(1, min(int(params.get("times", 1) or 1), _MAX_REPEAT))
        except (TypeError, ValueError):
            times = 1
        try:
            for i in range(times):
                _press(vk)
                if i + 1 < times:
                    time.sleep(0.05)
        except Exception as exc:
            return ToolResult(tool_name=self.tool_id, content=f"Could not send the key: {exc}", success=False)
        return ToolResult(
            tool_name=self.tool_id,
            content=f"Sent '{action}' x{times}. (I cannot see the player, so I cannot confirm the result.)",
            success=True,
            metadata={"action": action, "times": times},
        )
