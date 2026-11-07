"""Layer 3 / 4: Amazon Bedrock Guardrails (ApplyGuardrail) and model invocation (Converse)."""

from __future__ import annotations

from typing import Any

from ..pipeline import Verdict


def _contains_blocked(node: Any) -> bool:
    """True if any assessment entry carries action == BLOCKED.

    ApplyGuardrail reports GUARDRAIL_INTERVENED both for blocks and for masking
    (ANONYMIZED). Walking the assessments tells the two apart without depending on the
    exact nesting of each policy type.
    """
    if isinstance(node, dict):
        if node.get("action") == "BLOCKED":
            return True
        return any(_contains_blocked(v) for v in node.values())
    if isinstance(node, list):
        return any(_contains_blocked(v) for v in node)
    return False


class BedrockGuardrailLayer:
    def __init__(self, client: Any, guardrail_id: str, guardrail_version: str, source: str) -> None:
        if source not in ("INPUT", "OUTPUT"):
            raise ValueError("source must be INPUT or OUTPUT")
        self.name = f"bedrock_guardrail_{source.lower()}"
        self._client = client
        self._id = guardrail_id
        self._version = guardrail_version
        self._source = source

    def check(self, text: str, *, prompt: str | None = None) -> Verdict:
        block: dict[str, Any] = {"text": text}
        if self._source == "INPUT":
            # Prompt-attack detection only evaluates content tagged as guard content.
            block["qualifiers"] = ["guard_content"]

        resp = self._client.apply_guardrail(
            guardrailIdentifier=self._id,
            guardrailVersion=self._version,
            source=self._source,
            content=[{"text": block}],
        )

        if resp.get("action") != "GUARDRAIL_INTERVENED":
            return Verdict(True, text)

        if _contains_blocked(resp.get("assessments", [])):
            return Verdict(False, text, reason="blocked")

        # Intervened without a block means content was masked. Use the masked text.
        masked = "".join(o.get("text", "") for o in resp.get("outputs", []))
        return Verdict(True, masked or text, reason="masked")


class BedrockModel:
    def __init__(self, client: Any, model_id: str, system_prompt: str, max_tokens: int) -> None:
        self._client = client
        self._model_id = model_id
        self._system = [{"text": system_prompt}]
        self._max_tokens = max_tokens

    def generate(self, prompt: str) -> str:
        resp = self._client.converse(
            modelId=self._model_id,
            system=self._system,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": self._max_tokens, "temperature": 0.2},
        )
        parts = resp["output"]["message"]["content"]
        return "".join(p.get("text", "") for p in parts)
