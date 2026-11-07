"""Tests for the Presidio wrapper using fake presidio modules (no spaCy model needed)."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from gateway.layers.pii import PresidioRedactor


class FakeAnalyzer:
    findings: list = []
    last_kwargs: dict = {}

    def __init__(self, nlp_engine=None, supported_languages=None):
        self.nlp_engine = nlp_engine
        self.supported_languages = supported_languages

    def analyze(self, **kwargs):
        FakeAnalyzer.last_kwargs = kwargs
        return FakeAnalyzer.findings


class FakeAnonymizer:
    def anonymize(self, text, analyzer_results):
        redacted = text
        for f in sorted(analyzer_results, key=lambda r: r.start, reverse=True):
            redacted = redacted[: f.start] + f"<{f.entity_type}>" + redacted[f.end :]
        return SimpleNamespace(text=redacted)


class FakeProvider:
    config: dict = {}

    def __init__(self, nlp_configuration):
        FakeProvider.config = nlp_configuration

    def create_engine(self):
        return "engine"


@pytest.fixture
def presidio(monkeypatch):
    def module(name, **attrs):
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, mod)

    module("presidio_analyzer", AnalyzerEngine=FakeAnalyzer)
    module("presidio_analyzer.nlp_engine", NlpEngineProvider=FakeProvider)
    module("presidio_anonymizer", AnonymizerEngine=FakeAnonymizer)
    FakeAnalyzer.findings = []
    FakeAnalyzer.last_kwargs = {}
    return FakeAnalyzer


def finding(entity_type, start, end):
    return SimpleNamespace(entity_type=entity_type, start=start, end=end)


def test_no_findings_returns_text_unchanged(presidio):
    verdict = PresidioRedactor(("PERSON",)).check("nothing to see")
    assert verdict.allowed
    assert verdict.text == "nothing to see"
    assert verdict.reason is None


def test_redacts_and_reports_entity_counts_without_values(presidio):
    text = "mail bob@x.com or amy@y.com"
    presidio.findings = [finding("EMAIL_ADDRESS", 5, 14), finding("EMAIL_ADDRESS", 18, 27)]
    verdict = PresidioRedactor(("EMAIL_ADDRESS",)).check(text)

    assert verdict.allowed, "redaction sanitizes, it does not block"
    assert verdict.text == "mail <EMAIL_ADDRESS> or <EMAIL_ADDRESS>"
    assert verdict.reason == "redacted"
    assert verdict.details == {"entities": {"EMAIL_ADDRESS": 2}}
    assert "bob@x.com" not in str(verdict.details)


def test_passes_entities_and_threshold_to_analyzer(presidio):
    PresidioRedactor(("PERSON", "US_SSN"), score_threshold=0.7).check("hello")
    kwargs = presidio.last_kwargs
    assert kwargs["entities"] == ["PERSON", "US_SSN"]
    assert kwargs["score_threshold"] == 0.7
    assert kwargs["language"] == "en"


def test_uses_configured_spacy_model(presidio):
    PresidioRedactor(("PERSON",), spacy_model="en_core_web_md")
    assert FakeProvider.config["models"][0]["model_name"] == "en_core_web_md"


def test_layer_name_is_configurable_for_the_output_stage(presidio):
    assert PresidioRedactor(("PERSON",)).name == "pii_redaction"
    assert PresidioRedactor(("PERSON",), name="pii_redaction_output").name == "pii_redaction_output"
