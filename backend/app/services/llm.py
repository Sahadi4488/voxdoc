"""Groq chat completions that must answer in JSON, with typed errors.

complete_json() is the only way the app talks to an LLM:
- The reply is parsed and validated with a Pydantic model (never trust an
  LLM's output shape). Invalid JSON or the wrong shape is retried once, then
  raises LLMError.
- A reply cut off by max_completion_tokens (finish_reason "length") is an
  error, never an empty summary. gpt-oss is a reasoning model: its hidden
  reasoning counts against that budget too.
- SDK errors become our own: rate limit -> LLMBusy, bad key or no access to
  the model -> LLMNotConfigured, timeout / connection error / Groq outage ->
  LLMUnavailable. Responses carry only each error's public_message: never
  the key, never Groq's raw error text (that goes to the server log).

The SDK itself retries 429s, 5xx and connection errors, honouring
retry-after up to 60 s. max_retries=1 keeps a user from waiting through
several silent retries, so there's no retry loop of our own on top. The JSON
retry is different: that request succeeded, but its answer was unusable.

Every call logs its token usage: that's how the summary budget is checked.
"""
import logging
import math
import time
from functools import lru_cache
from typing import TypeVar

import groq
from pydantic import BaseModel, SecretStr, ValidationError

from app.config import settings

log = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)

TIMEOUT_S = 30
DEFAULT_RETRY_AFTER_S = 10  # a 429 without a retry-after header


class LLMError(Exception):
    """The AI answer was unusable. str(e) is the reason, for the server log;
    public_message is the only text a user ever sees."""

    status_code = 502
    public_message = "The AI service returned an unusable answer. Try again."


class LLMNotConfigured(LLMError):
    status_code = 503
    public_message = "AI features aren't configured on this server."


class LLMBusy(LLMError):
    status_code = 429

    def __init__(self, retry_after: int, reason: str = "rate limited"):
        super().__init__(reason)
        self.retry_after = retry_after

    @property
    def public_message(self) -> str:
        return f"The AI service is busy. Try again in {self.retry_after} seconds."


class LLMUnavailable(LLMError):
    status_code = 504
    public_message = "The AI service didn't respond. Try again in a moment."


class LLMClient:
    def __init__(self, api_key: SecretStr | None, client=None):
        """client: anything with Groq's chat.completions.create (tests pass a fake)."""
        if client is None and api_key is not None:
            client = groq.Groq(api_key=api_key.get_secret_value(), timeout=TIMEOUT_S, max_retries=1)
        self._client = client

    @property
    def configured(self) -> bool:
        return self._client is not None

    def require_configured(self) -> None:
        if self._client is None:
            raise LLMNotConfigured("no Groq API key (set VOXDOC_GROQ_API_KEY in backend/.env)")

    def complete_json(self, model: str, prompt: str, max_tokens: int, schema: type[M]) -> M:
        """One answer from `model`, validated as `schema`. Invalid JSON is retried once."""
        self.require_configured()
        for attempt in (1, 2):
            content = self._complete(model, prompt, max_tokens)
            if content is None:
                reason = "Groq's JSON mode rejected the output (json_validate_failed)"
            else:
                try:
                    return schema.model_validate_json(content)
                except ValidationError as e:
                    reason = f"{e.error_count()} validation error(s), first: {e.errors()[0]['msg']}"
            log.warning("%s answer unusable (attempt %d of 2): %s", model, attempt, reason)
        raise LLMError(f"{model} returned unusable JSON twice")

    def _complete(self, model: str, prompt: str, max_tokens: int) -> str | None:
        """One request. Returns the content, or None if Groq's JSON mode rejected it."""
        started = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(
                model=model,
                # Groq's reasoning guide: every instruction in the user message, no system prompt
                messages=[{"role": "user", "content": prompt}],
                reasoning_effort="low",  # few thinking tokens: they count against max_tokens
                include_reasoning=False,  # leave the reasoning text out of the response
                response_format={"type": "json_object"},
                max_completion_tokens=max_tokens,
                temperature=0.5,
            )
        except groq.RateLimitError as e:
            raise LLMBusy(_retry_after(e.response), _describe(e)) from None
        except (groq.AuthenticationError, groq.PermissionDeniedError, groq.NotFoundError) as e:
            # A bad key, or a model this account can't use (Llama is Enterprise-only now)
            raise LLMNotConfigured(_describe(e)) from None
        except groq.BadRequestError as e:
            if _error_code(e) == "json_validate_failed":
                return None
            raise LLMError(_describe(e)) from None
        except groq.InternalServerError as e:
            raise LLMUnavailable(_describe(e)) from None
        except groq.APIConnectionError as e:  # includes APITimeoutError
            raise LLMUnavailable(type(e).__name__) from None
        except groq.APIStatusError as e:  # anything else, e.g. 413 request too large
            raise LLMError(_describe(e)) from None

        choice = resp.choices[0]
        usage = resp.usage
        reasoning = getattr(getattr(usage, "completion_tokens_details", None), "reasoning_tokens", None)
        log.info("groq %s: %d prompt + %d completion tokens%s, %.2f s, finish_reason=%s",
                 model, usage.prompt_tokens, usage.completion_tokens,
                 f" ({reasoning} reasoning)" if reasoning is not None else "",
                 time.perf_counter() - started, choice.finish_reason)
        if choice.finish_reason == "length":
            raise LLMError(f"{model} used all {max_tokens} max_completion_tokens before finishing")
        return choice.message.content or ""


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Process-wide client (one connection pool); also the FastAPI dependency tests override."""
    return LLMClient(settings.groq_api_key)


def _retry_after(response) -> int:
    try:
        return max(1, math.ceil(float(response.headers["retry-after"])))
    except (KeyError, ValueError, TypeError, AttributeError):
        return DEFAULT_RETRY_AFTER_S


def _error_code(e: groq.APIStatusError) -> str | None:
    body = e.body if isinstance(e.body, dict) else {}
    err = body.get("error", body)
    return err.get("code") if isinstance(err, dict) else None


def _describe(e: groq.APIStatusError) -> str:
    """For the server log only."""
    return f"{type(e).__name__} {e.status_code}: {e.message}"
