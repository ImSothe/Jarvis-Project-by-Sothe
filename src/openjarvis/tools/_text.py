"""Small text helpers shared by tools."""

from __future__ import annotations

import re
from typing import Any

_UNSAFE_QUERY_CHARS = re.compile(r"[^\w\s.\-&'ñÑáéíóúÁÉÍÓÚüÜ]")


def clean_query(text: Any, max_len: int) -> str:
    """Reduce model-supplied search text to a short, safe string."""
    q = _UNSAFE_QUERY_CHARS.sub(" ", str(text or ""))
    return re.sub(r"\s+", " ", q).strip()[:max_len]
