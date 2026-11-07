"""Layer contract and the orchestration that chains layers together.

Every defensive layer implements ``Layer.check``. The pipeline runs layers in order, passes
the (possibly sanitized) text from one layer to the next, and stops at the first block.
A layer that raises fails closed unless it is explicitly listed in ``fail_open``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from . import audit


@dataclass
class Verdict:
    allowed: bool
    text: str
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class Layer(Protocol):
    name: str

    def check(self, text: str, *, prompt: str | None = None) -> Verdict:
        """Inspect ``text``. ``prompt`` is the sanitized user prompt (output layers only)."""
        ...


class Model(Protocol):
    def generate(self, prompt: str) -> str: ...


class ModelError(RuntimeError):
    """The foundation model call failed. Mapped to a 502 by the API layer."""


@dataclass
class StageResult:
    allowed: bool
    text: str
    blocked_by: str | None
    trace: list[dict[str, Any]]


def run_stage(
    layers: list[Layer],
    text: str,
    *,
    prompt: str | None = None,
    fail_open: frozenset[str] = frozenset(),
) -> StageResult:
    trace: list[dict[str, Any]] = []
    current = text

    for layer in layers:
        started = time.perf_counter()
        try:
            verdict = layer.check(current, prompt=prompt)
        except Exception as exc:  # noqa: BLE001 - any layer failure must be handled here
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            if layer.name in fail_open:
                trace.append({"layer": layer.name, "allowed": True, "ms": elapsed,
                              "error": type(exc).__name__, "fail_open": True})
                continue
            trace.append({"layer": layer.name, "allowed": False, "ms": elapsed,
                          "error": type(exc).__name__})
            return StageResult(False, current, layer.name, trace)

        elapsed = round((time.perf_counter() - started) * 1000, 1)
        entry: dict[str, Any] = {"layer": layer.name, "allowed": verdict.allowed, "ms": elapsed}
        if verdict.reason:
            entry["reason"] = verdict.reason
        if verdict.details:
            entry["details"] = verdict.details
        trace.append(entry)

        if not verdict.allowed:
            return StageResult(False, current, layer.name, trace)
        current = verdict.text

    return StageResult(True, current, None, trace)


@dataclass
class Result:
    blocked: bool
    text: str
    blocked_by: str | None = None


class GatewayService:
    """input layers -> model -> output layers, with an audit record per request."""

    def __init__(
        self,
        input_layers: list[Layer],
        output_layers: list[Layer],
        model: Model,
        *,
        fail_open: frozenset[str] = frozenset(),
        environment: str = "dev",
    ) -> None:
        self._input = input_layers
        self._output = output_layers
        self._model = model
        self._fail_open = fail_open
        self._environment = environment

    def handle(self, prompt: str, request_id: str) -> Result:
        started = time.perf_counter()
        base = {
            "request_id": request_id,
            "environment": self._environment,
            "prompt_sha256": audit.digest(prompt),
            "prompt_chars": len(prompt),
        }

        inbound = run_stage(self._input, prompt, fail_open=self._fail_open)
        if not inbound.allowed:
            audit.emit("request", outcome="blocked_input", blocked_by=inbound.blocked_by,
                       stages={"input": inbound.trace}, total_ms=_ms(started), **base)
            return Result(True, "", inbound.blocked_by)

        try:
            raw = self._model.generate(inbound.text)
        except Exception as exc:  # noqa: BLE001
            audit.emit("request", outcome="model_error", error=type(exc).__name__,
                       stages={"input": inbound.trace}, total_ms=_ms(started), **base)
            raise ModelError("model invocation failed") from exc

        outbound = run_stage(self._output, raw, prompt=inbound.text, fail_open=self._fail_open)
        if not outbound.allowed:
            audit.emit("request", outcome="blocked_output", blocked_by=outbound.blocked_by,
                       stages={"input": inbound.trace, "output": outbound.trace},
                       response_sha256=audit.digest(raw), total_ms=_ms(started), **base)
            return Result(True, "", outbound.blocked_by)

        audit.emit("request", outcome="allowed",
                   stages={"input": inbound.trace, "output": outbound.trace},
                   response_sha256=audit.digest(outbound.text), total_ms=_ms(started), **base)
        return Result(False, outbound.text)


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)
