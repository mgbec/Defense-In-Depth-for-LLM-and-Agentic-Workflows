import pytest

from gateway.config import DEFAULT_PII_ENTITIES, Settings

REQUIRED = {
    "API_KEY": "k",
    "GUARDRAIL_ID": "gr-1",
    "GUARDRAIL_VERSION": "2",
    "MODEL_ID": "m",
    "AWS_REGION": "eu-west-1",
}


@pytest.fixture
def env(monkeypatch):
    for key in list(REQUIRED) + [
        "FAIL_OPEN_LAYERS", "PII_ENTITIES", "MAX_PROMPT_CHARS", "BLOCK_ENCODED_BLOBS",
        "INJECTION_THRESHOLD", "ENVIRONMENT",
    ]:
        monkeypatch.delenv(key, raising=False)
    for key, value in REQUIRED.items():
        monkeypatch.setenv(key, value)
    return monkeypatch


def test_loads_required_values_and_defaults(env):
    s = Settings.from_env()
    assert (s.api_key, s.guardrail_id, s.guardrail_version, s.model_id, s.region) == (
        "k", "gr-1", "2", "m", "eu-west-1",
    )
    assert s.max_prompt_chars == 8000
    assert s.pii_entities == DEFAULT_PII_ENTITIES
    assert s.fail_open_layers == frozenset()


@pytest.mark.parametrize("missing", list(REQUIRED))
def test_missing_required_variable_fails_fast(env, missing):
    env.delenv(missing)
    with pytest.raises(RuntimeError, match=missing):
        Settings.from_env()


def test_blank_required_variable_counts_as_missing(env):
    env.setenv("API_KEY", "   ")
    with pytest.raises(RuntimeError, match="API_KEY"):
        Settings.from_env()


def test_csv_values_are_trimmed(env):
    env.setenv("FAIL_OPEN_LAYERS", " a , b ,, ")
    env.setenv("PII_ENTITIES", "PERSON, EMAIL_ADDRESS")
    s = Settings.from_env()
    assert s.fail_open_layers == frozenset({"a", "b"})
    assert s.pii_entities == ("PERSON", "EMAIL_ADDRESS")


def test_numeric_and_boolean_overrides(env):
    env.setenv("MAX_PROMPT_CHARS", "500")
    env.setenv("INJECTION_THRESHOLD", "0.75")
    env.setenv("BLOCK_ENCODED_BLOBS", "FALSE")
    s = Settings.from_env()
    assert s.max_prompt_chars == 500
    assert s.injection_threshold == 0.75
    assert s.block_encoded_blobs is False
