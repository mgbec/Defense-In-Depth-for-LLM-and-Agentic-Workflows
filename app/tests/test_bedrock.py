import pytest

from gateway.layers.bedrock import BedrockGuardrailLayer, BedrockModel, _contains_blocked


# ---------------------------------------------------------------- _contains_blocked
@pytest.mark.parametrize(
    "assessments, expected",
    [
        ([], False),
        ([{}], False),
        ([{"contentPolicy": {"filters": [{"action": "BLOCKED"}]}}], True),
        ([{"sensitiveInformationPolicy": {"piiEntities": [{"action": "ANONYMIZED"}]}}], False),
        (
            [{"a": {"piiEntities": [{"action": "ANONYMIZED"}]}, "b": {"topics": [{"action": "BLOCKED"}]}}],
            True,
        ),
        ([{"deeply": {"nested": [{"list": [{"action": "BLOCKED"}]}]}}], True),
        ([{"action": "NONE"}], False),
    ],
)
def test_contains_blocked(assessments, expected):
    assert _contains_blocked(assessments) is expected


# ---------------------------------------------------------------- guardrail layer
def test_rejects_invalid_source(bedrock):
    with pytest.raises(ValueError):
        BedrockGuardrailLayer(bedrock, "g", "1", "SIDEWAYS")


def test_layer_names_reflect_source(bedrock):
    assert BedrockGuardrailLayer(bedrock, "g", "1", "INPUT").name == "bedrock_guardrail_input"
    assert BedrockGuardrailLayer(bedrock, "g", "1", "OUTPUT").name == "bedrock_guardrail_output"


def test_no_intervention_passes_text_through(bedrock):
    layer = BedrockGuardrailLayer(bedrock, "gr-1", "3", "INPUT")
    verdict = layer.check("hello")
    assert verdict.allowed
    assert verdict.text == "hello"


def test_request_uses_pinned_id_and_version(bedrock):
    BedrockGuardrailLayer(bedrock, "gr-1", "3", "INPUT").check("hello")
    call = bedrock.guard_calls[0]
    assert call["guardrailIdentifier"] == "gr-1"
    assert call["guardrailVersion"] == "3"
    assert call["source"] == "INPUT"


def test_input_is_tagged_as_guard_content(bedrock):
    BedrockGuardrailLayer(bedrock, "g", "1", "INPUT").check("hello")
    assert bedrock.guard_calls[0]["content"][0]["text"]["qualifiers"] == ["guard_content"]


def test_output_is_not_tagged(bedrock):
    BedrockGuardrailLayer(bedrock, "g", "1", "OUTPUT").check("hello")
    assert "qualifiers" not in bedrock.guard_calls[0]["content"][0]["text"]


def test_block_is_reported_as_not_allowed(bedrock):
    bedrock.guard_mode = "block"
    verdict = BedrockGuardrailLayer(bedrock, "g", "1", "INPUT").check("bad")
    assert not verdict.allowed
    assert verdict.reason == "blocked"


def test_masking_is_allowed_and_uses_masked_text(bedrock):
    bedrock.guard_mode = "mask"
    verdict = BedrockGuardrailLayer(bedrock, "g", "1", "OUTPUT").check("mail me at a@b.com")
    assert verdict.allowed
    assert verdict.text == "masked {EMAIL}"
    assert verdict.reason == "masked"


def test_masking_with_no_output_text_falls_back_to_original(bedrock):
    class Client:
        def apply_guardrail(self, **_):
            return {
                "action": "GUARDRAIL_INTERVENED",
                "outputs": [],
                "assessments": [{"p": [{"action": "ANONYMIZED"}]}],
            }

    verdict = BedrockGuardrailLayer(Client(), "g", "1", "OUTPUT").check("original")
    assert verdict.allowed
    assert verdict.text == "original"


def test_aws_errors_propagate_so_the_pipeline_can_fail_closed():
    class Client:
        def apply_guardrail(self, **_):
            raise RuntimeError("AccessDenied")

    with pytest.raises(RuntimeError):
        BedrockGuardrailLayer(Client(), "g", "1", "INPUT").check("x")


# ---------------------------------------------------------------- model
def test_model_sends_system_prompt_and_user_message(bedrock):
    model = BedrockModel(bedrock, "model-x", "be nice", 256)
    model.generate("hi there")
    call = bedrock.converse_calls[0]

    assert call["modelId"] == "model-x"
    assert call["system"] == [{"text": "be nice"}]
    assert call["messages"] == [{"role": "user", "content": [{"text": "hi there"}]}]
    assert call["inferenceConfig"]["maxTokens"] == 256


def test_model_joins_multiple_text_blocks():
    class Client:
        def converse(self, **_):
            return {"output": {"message": {"content": [{"text": "one "}, {"toolUse": {}}, {"text": "two"}]}}}

    assert BedrockModel(Client(), "m", "s", 10).generate("x") == "one two"
