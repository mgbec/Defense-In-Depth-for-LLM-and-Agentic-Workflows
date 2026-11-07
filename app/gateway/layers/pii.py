"""Layer 2a: PII redaction with Microsoft Presidio.

Runs before any text leaves the service boundary (managed guardrail, model), so PII is
replaced with entity placeholders such as <PERSON> before egress.
"""

from __future__ import annotations

from collections import Counter

from ..pipeline import Verdict


class PresidioRedactor:
    def __init__(
        self,
        entities: tuple[str, ...],
        score_threshold: float = 0.5,
        *,
        name: str = "pii_redaction",
        spacy_model: str = "en_core_web_sm",
    ) -> None:
        # Imported lazily so the module can be imported (and unit tested) without the
        # heavy NLP stack installed.
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        from presidio_anonymizer import AnonymizerEngine

        nlp_engine = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": spacy_model}],
            }
        ).create_engine()

        self.name = name
        self._entities = list(entities)
        self._threshold = score_threshold
        self._analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
        self._anonymizer = AnonymizerEngine()

    def check(self, text: str, *, prompt: str | None = None) -> Verdict:
        findings = self._analyzer.analyze(
            text=text,
            language="en",
            entities=self._entities,
            score_threshold=self._threshold,
        )
        if not findings:
            return Verdict(True, text)

        redacted = self._anonymizer.anonymize(text=text, analyzer_results=findings).text
        counts = dict(Counter(f.entity_type for f in findings))
        return Verdict(True, redacted, reason="redacted", details={"entities": counts})
