"""Assembles the production layer stack in defense-in-depth order."""

from __future__ import annotations

import boto3
from botocore.config import Config

from .config import Settings
from .layers.bedrock import BedrockGuardrailLayer, BedrockModel
from .layers.llmguard import LLMGuardInput, LLMGuardOutput
from .layers.pii import PresidioRedactor
from .layers.prefilter import PreFilter
from .pipeline import GatewayService


def build_service(settings: Settings) -> GatewayService:
    client = boto3.client(
        "bedrock-runtime",
        region_name=settings.region,
        config=Config(
            connect_timeout=5,
            read_timeout=settings.aws_timeout_seconds,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )

    # Input: cheapest and most deterministic first, managed policy last before the model.
    input_layers = [
        PreFilter(settings.max_prompt_chars, settings.block_encoded_blobs),
        PresidioRedactor(settings.pii_entities, settings.pii_score_threshold),
        LLMGuardInput(settings.injection_threshold, settings.toxicity_threshold),
        BedrockGuardrailLayer(client, settings.guardrail_id, settings.guardrail_version, "INPUT"),
    ]

    output_layers = [
        BedrockGuardrailLayer(client, settings.guardrail_id, settings.guardrail_version, "OUTPUT"),
        LLMGuardOutput(settings.toxicity_threshold),
    ]
    if settings.redact_output_pii:
        output_layers.append(
            PresidioRedactor(
                settings.pii_entities, settings.pii_score_threshold, name="pii_redaction_output"
            )
        )

    model = BedrockModel(client, settings.model_id, settings.system_prompt, settings.max_output_tokens)

    return GatewayService(
        input_layers,
        output_layers,
        model,
        fail_open=settings.fail_open_layers,
        environment=settings.environment,
    )
