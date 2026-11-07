"""Shared fakes. Nothing here needs AWS credentials, model weights, or network access."""

from __future__ import annotations

import pytest

from gateway.config import Settings
from gateway.pipeline import Verdict


class FakeBedrock:
    """Stands in for the bedrock-runtime client."""

    def __init__(self) -> None:
        self.guard_calls: list[dict] = []
        self.converse_calls: list[dict] = []
        self.guard_mode = "none"  # none | block | mask
        self.model_text = "TCP is connection oriented."
        self.model_error: Exception | None = None

    def apply_guardrail(self, **kwargs):
        self.guard_calls.append(kwargs)
        if self.guard_mode == "block":
            return {
                "action": "GUARDRAIL_INTERVENED",
                "outputs": [{"text": "blocked message"}],
                "assessments": [{"contentPolicy": {"filters": [{"action": "BLOCKED"}]}}],
            }
        if self.guard_mode == "mask":
            return {
                "action": "GUARDRAIL_INTERVENED",
                "outputs": [{"text": "masked {EMAIL}"}],
                "assessments": [
                    {"sensitiveInformationPolicy": {"piiEntities": [{"action": "ANONYMIZED"}]}}
                ],
            }
        return {"action": "NONE", "outputs": [], "assessments": []}

    def converse(self, **kwargs):
        self.converse_calls.append(kwargs)
        if self.model_error:
            raise self.model_error
        return {"output": {"message": {"content": [{"text": self.model_text}]}}}


class StaticLayer:
    """A configurable layer for pipeline tests."""

    def __init__(self, name: str, *, allowed: bool = True, transform=None, raises=None) -> None:
        self.name = name
        self.calls: list[tuple[str, str | None]] = []
        self._allowed = allowed
        self._transform = transform or (lambda t: t)
        self._raises = raises

    def check(self, text: str, *, prompt: str | None = None) -> Verdict:
        self.calls.append((text, prompt))
        if self._raises:
            raise self._raises
        return Verdict(self._allowed, self._transform(text), reason=None if self._allowed else "no")


@pytest.fixture
def audit_lines():
    """Collects emitted audit records. The module's stdout handler binds sys.stdout at
    import time, so capsys cannot see it; attach a handler to the logger instead."""
    import logging

    records: list[str] = []

    class ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    logger = logging.getLogger("gateway.audit")
    handler = ListHandler()
    logger.addHandler(handler)
    yield records
    logger.removeHandler(handler)


@pytest.fixture
def bedrock() -> FakeBedrock:
    return FakeBedrock()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        api_key="test-key",
        guardrail_id="gr-123",
        guardrail_version="1",
        model_id="model-x",
        region="us-east-1",
    )
