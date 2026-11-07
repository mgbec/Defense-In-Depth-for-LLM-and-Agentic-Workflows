"""Layer 1: fast deterministic pre-filter (no model inference, sub-millisecond).

This is a cheap first pass, not a defense on its own: regex denylists are easy to evade.
Its job is to normalize input, enforce size limits, and reject obvious junk before the
expensive layers run.
"""

from __future__ import annotations

import re
import unicodedata

from ..pipeline import Verdict

# Zero-width and bidi control characters commonly used to smuggle or obfuscate instructions.
_INVISIBLE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ENCODED_BLOB = re.compile(r"[A-Za-z0-9+/_-]{200,}={0,2}")

_DENYLIST = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(all\s+)?(the\s+)?(previous|prior|above|earlier)\s+(instructions|prompts?|rules)",
        r"disregard\s+.{0,40}\b(system|developer)\s+(prompt|message|instructions)",
        r"(reveal|print|repeat|show)\s+.{0,40}\b(system|hidden|initial)\s+prompt",
        r"you\s+are\s+now\s+(in\s+)?(dan|developer\s+mode|jailbroken)",
    )
]


class PreFilter:
    name = "prefilter"

    def __init__(self, max_chars: int, block_encoded_blobs: bool = True) -> None:
        self._max_chars = max_chars
        self._block_blobs = block_encoded_blobs

    def check(self, text: str, *, prompt: str | None = None) -> Verdict:
        normalized = unicodedata.normalize("NFKC", text)
        normalized = _INVISIBLE.sub("", normalized)
        normalized = _CONTROL.sub("", normalized).strip()

        if not normalized:
            return Verdict(False, normalized, reason="empty")
        if len(normalized) > self._max_chars:
            return Verdict(False, normalized, reason="too_long")
        if self._block_blobs and _ENCODED_BLOB.search(normalized):
            return Verdict(False, normalized, reason="encoded_blob")
        for pattern in _DENYLIST:
            if pattern.search(normalized):
                return Verdict(False, normalized, reason="denylist")

        return Verdict(True, normalized)
