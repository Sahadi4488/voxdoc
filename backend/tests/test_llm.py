import logging

import groq
import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.services.llm import DEFAULT_RETRY_AFTER_S, LLMBusy, LLMClient, LLMError, LLMNotConfigured, LLMUnavailable
from app.services.summarizer import SummaryJSON
from tests.conftest import SUMMARY, FakeGroq

REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def status_error(cls, status, headers=None, body=None, message="Error code: raw Groq text"):
    """An SDK exception exactly as the Groq client raises it."""
    return cls(message, response=httpx.Response(status, headers=headers or {}, request=REQUEST), body=body)


def make_llm(*replies):
    fake = FakeGroq(*replies)
    return LLMClient(SecretStr("test-key"), client=fake), fake


def ask(llm):
    return llm.complete_json("openai/gpt-oss-20b", "Summarize this.", 1200, SummaryJSON)


def test_valid_answer_is_parsed_and_validated():
    llm, fake = make_llm()
    assert ask(llm) == SummaryJSON(**SUMMARY)
    req = fake.requests[0]
    assert req["model"] == "openai/gpt-oss-20b"
    assert req["reasoning_effort"] == "low" and req["include_reasoning"] is False
    assert req["response_format"] == {"type": "json_object"} and req["max_completion_tokens"] == 1200
    assert [m["role"] for m in req["messages"]] == ["user"]  # no system prompt (Groq's reasoning guide)


def test_invalid_json_is_retried_once_then_succeeds():
    llm, fake = make_llm("Here is your summary: {", SUMMARY)
    assert ask(llm).overview == SUMMARY["overview"]
    assert len(fake.requests) == 2


@pytest.mark.parametrize("bad", [
    "not json {",
    "",
    {"overview": "Missing the key points."},  # valid JSON, wrong shape
    {"overview": "  ", "key_points": ["x"]},
    {"overview": "Fine.", "key_points": []},
])
def test_unusable_answer_twice_is_a_clean_error(bad):
    llm, fake = make_llm(bad)
    with pytest.raises(LLMError) as e:
        ask(llm)
    assert type(e.value) is LLMError and len(fake.requests) == 2


def test_groq_json_mode_rejection_counts_as_invalid_json():
    rejected = status_error(groq.BadRequestError, 400, body={"error": {
        "message": "Failed to generate JSON.", "type": "invalid_request_error", "code": "json_validate_failed"}})
    llm, fake = make_llm(rejected, SUMMARY)
    assert ask(llm).overview == SUMMARY["overview"]
    assert len(fake.requests) == 2


@pytest.mark.parametrize("content", ["", '{"overview": "The document descr'])
def test_finish_reason_length_is_an_error_not_an_empty_summary(content):
    llm, fake = make_llm((content, "length"))
    with pytest.raises(LLMError):
        ask(llm)
    assert len(fake.requests) == 1  # not retried: the same budget would run out again


@pytest.mark.parametrize("header, expected", [("7", 7), ("2.3", 3), (None, DEFAULT_RETRY_AFTER_S)])
def test_rate_limit_becomes_busy_with_retry_after(header, expected):
    llm, _ = make_llm(status_error(groq.RateLimitError, 429, headers={"retry-after": header} if header else {}))
    with pytest.raises(LLMBusy) as e:
        ask(llm)
    assert e.value.retry_after == expected
    assert e.value.public_message == f"The AI service is busy. Try again in {expected} seconds."


@pytest.mark.parametrize("error, expected", [
    (status_error(groq.AuthenticationError, 401), LLMNotConfigured),
    (status_error(groq.PermissionDeniedError, 403), LLMNotConfigured),  # model not on this plan
    (status_error(groq.NotFoundError, 404), LLMNotConfigured),  # model name wrong or retired
    (groq.APITimeoutError(request=REQUEST), LLMUnavailable),
    (groq.APIConnectionError(request=REQUEST), LLMUnavailable),
    (status_error(groq.InternalServerError, 500), LLMUnavailable),
    (status_error(groq.APIStatusError, 413), LLMError),
    (status_error(groq.BadRequestError, 400, body={"error": {"code": "context_length_exceeded"}}), LLMError),
])
def test_sdk_errors_become_typed_errors(error, expected):
    llm, fake = make_llm(error)
    with pytest.raises(LLMError) as e:
        ask(llm)
    assert type(e.value) is expected
    assert len(fake.requests) == 1  # no retry loop of our own on top of the SDK's


def test_no_key_is_not_configured():
    llm = LLMClient(None)
    assert not llm.configured
    with pytest.raises(LLMNotConfigured):
        ask(llm)


def test_real_client_keeps_sdk_retries_and_timeout_low():
    sdk = LLMClient(SecretStr("gsk_not_a_real_key"))._client
    assert sdk.max_retries == 1 and sdk.timeout == 30 and sdk.api_key == "gsk_not_a_real_key"


def test_token_usage_is_logged(caplog):
    llm, _ = make_llm()
    with caplog.at_level(logging.INFO, logger="app.services.llm"):
        ask(llm)
    assert "prompt + 100 completion tokens (40 reasoning)" in caplog.text


def test_settings_never_print_the_key(tmp_path):
    s = Settings(groq_api_key="gsk_secret_value_123", data_dir=tmp_path)
    assert s.groq_api_key.get_secret_value() == "gsk_secret_value_123"
    assert "gsk_secret" not in repr(s) and "gsk_secret" not in str(s.model_dump())


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_key_means_not_configured(tmp_path, blank):
    assert Settings(groq_api_key=blank, data_dir=tmp_path).groq_api_key is None
