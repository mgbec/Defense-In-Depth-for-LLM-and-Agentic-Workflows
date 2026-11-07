"""Structured audit logging.

One JSON line per request on stdout (shipped to CloudWatch by the ECS log driver).
Raw prompts and responses are never logged, only a SHA-256 digest and length, so the
audit trail does not become a second copy of sensitive data.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
from typing import Any

_logger = logging.getLogger("gateway.audit")
if not _logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def emit(event: str, **fields: Any) -> None:
    record = {"ts": round(time.time(), 3), "event": event, **fields}
    _logger.info(json.dumps(record, default=str, separators=(",", ":")))
