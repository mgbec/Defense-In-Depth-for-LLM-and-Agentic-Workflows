import pytest

from gateway.pipeline import GatewayService, ModelError, run_stage
from tests.conftest import StaticLayer


class EchoModel:
    def __init__(self, reply: str = "model reply") -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.reply


class FailingModel:
    def generate(self, prompt: str) -> str:
        raise RuntimeError("throttled")


# ---------------------------------------------------------------- run_stage
def test_run_stage_passes_text_between_layers():
    first = StaticLayer("first", transform=str.upper)
    second = StaticLayer("second", transform=lambda t: t + "!")
    result = run_stage([first, second], "abc")

    assert result.allowed
    assert result.text == "ABC!"
    assert second.calls[0][0] == "ABC"
    assert [t["layer"] for t in result.trace] == ["first", "second"]


def test_run_stage_stops_at_first_block():
    blocker = StaticLayer("blocker", allowed=False)
    after = StaticLayer("after")
    result = run_stage([StaticLayer("before"), blocker, after], "x")

    assert not result.allowed
    assert result.blocked_by == "blocker"
    assert after.calls == []


def test_run_stage_block_keeps_pre_block_text():
    result = run_stage(
        [StaticLayer("upper", transform=str.upper), StaticLayer("blocker", allowed=False)], "abc"
    )
    assert result.text == "ABC"


def test_layer_exception_fails_closed_by_default():
    boom = StaticLayer("boom", raises=RuntimeError("crash"))
    after = StaticLayer("after")
    result = run_stage([boom, after], "x")

    assert not result.allowed
    assert result.blocked_by == "boom"
    assert result.trace[0]["error"] == "RuntimeError"
    assert after.calls == []


def test_layer_exception_can_fail_open_when_listed():
    boom = StaticLayer("boom", raises=RuntimeError("crash"))
    after = StaticLayer("after")
    result = run_stage([boom, after], "x", fail_open=frozenset({"boom"}))

    assert result.allowed
    assert result.trace[0]["fail_open"] is True
    assert len(after.calls) == 1


def test_fail_open_only_applies_to_listed_layers():
    result = run_stage(
        [StaticLayer("a", raises=ValueError("x"))], "x", fail_open=frozenset({"other"})
    )
    assert not result.allowed


def test_output_layers_receive_the_prompt():
    layer = StaticLayer("out")
    run_stage([layer], "response", prompt="the prompt")
    assert layer.calls == [("response", "the prompt")]


def test_trace_records_reason_and_latency():
    result = run_stage([StaticLayer("blocker", allowed=False)], "x")
    entry = result.trace[0]
    assert entry["reason"] == "no"
    assert isinstance(entry["ms"], float)


# ---------------------------------------------------------------- GatewayService
def make_service(input_layers=(), output_layers=(), model=None, **kwargs):
    return GatewayService(list(input_layers), list(output_layers), model or EchoModel(), **kwargs)


def test_happy_path_returns_model_text():
    service = make_service(model=EchoModel("hello back"))
    result = service.handle("hello", "req-1")
    assert not result.blocked
    assert result.text == "hello back"


def test_sanitized_prompt_is_what_reaches_the_model():
    model = EchoModel()
    service = make_service([StaticLayer("redact", transform=lambda t: t.replace("secret", "<X>"))],
                           model=model)
    service.handle("my secret", "req-1")
    assert model.prompts == ["my <X>"]


def test_blocked_input_never_calls_the_model():
    model = EchoModel()
    service = make_service([StaticLayer("blocker", allowed=False)], model=model)
    result = service.handle("bad", "req-1")

    assert result.blocked
    assert result.blocked_by == "blocker"
    assert result.text == ""
    assert model.prompts == []


def test_blocked_output_withholds_the_response():
    service = make_service(output_layers=[StaticLayer("out", allowed=False)],
                           model=EchoModel("sensitive answer"))
    result = service.handle("hi", "req-1")

    assert result.blocked
    assert result.blocked_by == "out"
    assert "sensitive" not in result.text


def test_output_layers_get_sanitized_prompt_as_context():
    out = StaticLayer("out")
    service = make_service([StaticLayer("in", transform=str.upper)], [out])
    service.handle("abc", "req-1")
    assert out.calls[0][1] == "ABC"


def test_output_transformations_are_returned():
    service = make_service(output_layers=[StaticLayer("redact", transform=lambda t: "[redacted]")])
    assert service.handle("hi", "req-1").text == "[redacted]"


def test_model_failure_raises_model_error():
    service = make_service(model=FailingModel())
    with pytest.raises(ModelError):
        service.handle("hi", "req-1")


def test_audit_record_never_contains_plaintext(audit_lines):
    service = make_service(model=EchoModel("the secret answer"))
    service.handle("my confidential prompt", "req-42")
    assert len(audit_lines) == 1
    logged = audit_lines[0]

    assert "req-42" in logged
    assert "confidential" not in logged
    assert "secret answer" not in logged
    assert "prompt_sha256" in logged


def test_audit_record_names_the_blocking_layer(audit_lines):
    service = make_service([StaticLayer("blocker", allowed=False)])
    service.handle("x", "req-7")
    logged = audit_lines[0]
    assert '"blocked_by":"blocker"' in logged
    assert '"outcome":"blocked_input"' in logged
