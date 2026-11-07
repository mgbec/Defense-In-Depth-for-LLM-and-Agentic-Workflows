"""Tests for the LLM Guard wrappers.

LLM Guard needs torch and downloaded model weights, so a fake ``llm_guard`` package is
injected. These tests cover OUR logic (how scanner results are interpreted), not the
accuracy of LLM Guard's models.
"""

from __future__ import annotations

import sys
import types

import pytest

from gateway.layers.llmguard import LLMGuardInput, LLMGuardOutput


class FakeScanner:
    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs


class Secrets(FakeScanner): ...
class PromptInjection(FakeScanner): ...
class Toxicity(FakeScanner): ...
class Sensitive(FakeScanner): ...


class Recorder:
    """Controls what the fake scan_prompt / scan_output return."""

    def __init__(self):
        self.sanitized = None
        self.valid: dict[str, bool] = {}
        self.scores: dict[str, float] = {}
        self.calls: list[dict] = []

    def scan_prompt(self, scanners, text, fail_fast=False):
        self.calls.append({"kind": "prompt", "scanners": scanners, "text": text, "fail_fast": fail_fast})
        return (self.sanitized if self.sanitized is not None else text), self.valid, self.scores

    def scan_output(self, scanners, prompt, text, fail_fast=False):
        self.calls.append(
            {"kind": "output", "scanners": scanners, "prompt": prompt, "text": text, "fail_fast": fail_fast}
        )
        return (self.sanitized if self.sanitized is not None else text), self.valid, self.scores


@pytest.fixture
def llm_guard(monkeypatch):
    recorder = Recorder()

    def module(name, **attrs):
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, mod)
        return mod

    module("llm_guard", scan_prompt=recorder.scan_prompt, scan_output=recorder.scan_output)
    module("llm_guard.input_scanners", PromptInjection=PromptInjection, Secrets=Secrets, Toxicity=Toxicity)
    module("llm_guard.input_scanners.prompt_injection", MatchType=types.SimpleNamespace(FULL="FULL"))
    module("llm_guard.output_scanners", Sensitive=Sensitive, Toxicity=Toxicity)
    return recorder


# ---------------------------------------------------------------- input
def test_input_builds_scanners_cheapest_first_with_thresholds(llm_guard):
    layer = LLMGuardInput(injection_threshold=0.8, toxicity_threshold=0.6)
    kinds = [type(s).__name__ for s in layer._scanners]
    assert kinds == ["Secrets", "PromptInjection", "Toxicity"]
    assert layer._scanners[1].kwargs == {"threshold": 0.8, "match_type": "FULL"}
    assert layer._scanners[2].kwargs == {"threshold": 0.6}


def test_input_allows_clean_text_and_returns_sanitized(llm_guard):
    llm_guard.valid = {"Secrets": True, "PromptInjection": True, "Toxicity": True}
    llm_guard.sanitized = "cleaned"
    verdict = LLMGuardInput(0.9, 0.7).check("original")

    assert verdict.allowed
    assert verdict.text == "cleaned"
    assert llm_guard.calls[0]["fail_fast"] is True


def test_input_blocks_and_reports_failed_scanner_scores(llm_guard):
    llm_guard.valid = {"Secrets": True, "PromptInjection": False}
    llm_guard.scores = {"Secrets": 0.0, "PromptInjection": 0.97}
    verdict = LLMGuardInput(0.9, 0.7).check("ignore everything")

    assert not verdict.allowed
    assert verdict.details["scanners"] == ["PromptInjection"]
    assert verdict.details["scores"] == {"PromptInjection": 0.97}


def test_input_block_returns_original_text_not_sanitized(llm_guard):
    llm_guard.valid = {"Secrets": False}
    llm_guard.sanitized = "[REDACTED]"
    verdict = LLMGuardInput(0.9, 0.7).check("AKIA...")
    assert not verdict.allowed
    assert verdict.text == "AKIA..."


# ---------------------------------------------------------------- output
def test_output_passes_prompt_context_to_scanners(llm_guard):
    llm_guard.valid = {"Sensitive": True, "Toxicity": True}
    LLMGuardOutput(0.7).check("answer", prompt="question")
    assert llm_guard.calls[0]["prompt"] == "question"
    assert llm_guard.calls[0]["text"] == "answer"


def test_output_missing_prompt_defaults_to_empty_string(llm_guard):
    llm_guard.valid = {"Sensitive": True}
    LLMGuardOutput(0.7).check("answer")
    assert llm_guard.calls[0]["prompt"] == ""


def test_output_clean_is_allowed(llm_guard):
    llm_guard.valid = {"Sensitive": True, "Toxicity": True}
    verdict = LLMGuardOutput(0.7).check("fine")
    assert verdict.allowed
    assert verdict.reason is None


def test_output_sensitive_only_is_redacted_not_blocked(llm_guard):
    llm_guard.valid = {"Sensitive": False}
    llm_guard.sanitized = "contact <EMAIL_ADDRESS>"
    verdict = LLMGuardOutput(0.7).check("contact a@b.com")

    assert verdict.allowed
    assert verdict.text == "contact <EMAIL_ADDRESS>"
    assert verdict.reason == "redacted"


def test_output_toxicity_blocks(llm_guard):
    llm_guard.valid = {"Sensitive": True, "Toxicity": False}
    llm_guard.scores = {"Toxicity": 0.99}
    verdict = LLMGuardOutput(0.7).check("rude text")

    assert not verdict.allowed
    assert verdict.details["scanners"] == ["Toxicity"]


def test_output_sensitive_plus_other_failure_blocks(llm_guard):
    llm_guard.valid = {"Sensitive": False, "Toxicity": False}
    verdict = LLMGuardOutput(0.7).check("text")
    assert not verdict.allowed
