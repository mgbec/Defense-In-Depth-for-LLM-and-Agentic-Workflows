"""Layer 2b / 5b: LLM Guard scanners (Protect AI, MIT licensed), self-hosted.

Input:  Secrets -> PromptInjection -> Toxicity
Output: Sensitive -> Toxicity

Models are loaded once at construction. In the container image they are baked in at build
time and the service runs with HF_HUB_OFFLINE=1, so there is no runtime model download.
"""

from __future__ import annotations

from ..pipeline import Verdict


def _failed(results_valid: dict[str, bool]) -> list[str]:
    return [name for name, ok in results_valid.items() if not ok]


class LLMGuardInput:
    name = "llm_guard_input"

    def __init__(self, injection_threshold: float, toxicity_threshold: float) -> None:
        from llm_guard.input_scanners import PromptInjection, Secrets, Toxicity
        from llm_guard.input_scanners.prompt_injection import MatchType

        # Cheapest scanner first; fail_fast stops at the first failure.
        self._scanners = [
            Secrets(),
            PromptInjection(threshold=injection_threshold, match_type=MatchType.FULL),
            Toxicity(threshold=toxicity_threshold),
        ]

    def check(self, text: str, *, prompt: str | None = None) -> Verdict:
        from llm_guard import scan_prompt

        sanitized, valid, scores = scan_prompt(self._scanners, text, fail_fast=True)
        failed = _failed(valid)
        if failed:
            return Verdict(False, text, reason="scanner_failed",
                           details={"scanners": failed,
                                    "scores": {k: scores[k] for k in failed if k in scores}})
        return Verdict(True, sanitized)


class LLMGuardOutput:
    name = "llm_guard_output"

    def __init__(self, toxicity_threshold: float) -> None:
        from llm_guard.output_scanners import Sensitive, Toxicity

        self._scanners = [Sensitive(redact=True), Toxicity(threshold=toxicity_threshold)]

    def check(self, text: str, *, prompt: str | None = None) -> Verdict:
        from llm_guard import scan_output

        sanitized, valid, scores = scan_output(
            self._scanners, prompt or "", text, fail_fast=True
        )
        failed = _failed(valid)

        # Sensitive redacts in place: if that is the only finding, ship the redacted text
        # rather than blocking a useful answer. Any other finding blocks.
        if failed == ["Sensitive"]:
            return Verdict(True, sanitized, reason="redacted", details={"scanners": failed})
        if failed:
            return Verdict(False, text, reason="scanner_failed",
                           details={"scanners": failed,
                                    "scores": {k: scores[k] for k in failed if k in scores}})
        return Verdict(True, sanitized)
