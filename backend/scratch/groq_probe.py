"""Day 12 Part B: check the gpt-oss request parameters with your key before
llm.py relies on them. Prints the reply, finish_reason, token usage and the
rate-limit headers (the real free-plan limits for this key).

    python scratch\\groq_probe.py

The key comes from backend/.env (VOXDOC_GROQ_API_KEY) and is never printed.
Costs 3 small requests (~1,000 tokens).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import groq  # noqa: E402

from app.config import settings  # noqa: E402

PROMPT = ('Reply with only a JSON object {"overview": "...", "key_points": ["..."]} summarizing this text: '
          '"VoxDoc reads PDF and Word documents aloud and highlights each word as it is spoken. '
          'It runs on an ordinary laptop without a GPU."')


def call(client, model, max_tokens):
    started = time.perf_counter()
    try:
        raw = client.chat.completions.with_raw_response.create(
            model=model,
            messages=[{"role": "user", "content": PROMPT}],
            reasoning_effort="low",
            include_reasoning=False,
            response_format={"type": "json_object"},
            max_completion_tokens=max_tokens,
            temperature=0.5,
        )
    except groq.APIStatusError as e:
        error = e.body.get("error", {}) if isinstance(e.body, dict) else {}
        print(f"  {type(e).__name__} {e.status_code}, code={error.get('code')!r}")
        return
    resp = raw.parse()
    choice, usage, h = resp.choices[0], resp.usage, raw.headers
    reasoning = getattr(usage.completion_tokens_details, "reasoning_tokens", None)
    print(f"  {time.perf_counter() - started:.2f} s, finish_reason={choice.finish_reason}, "
          f"{usage.prompt_tokens} prompt + {usage.completion_tokens} completion tokens ({reasoning} reasoning)")
    print(f"  reasoning text in the response: {getattr(choice.message, 'reasoning', None) is not None}")
    print(f"  content: {choice.message.content!r}")
    print(f"  limits: {h.get('x-ratelimit-limit-requests')} requests/day, {h.get('x-ratelimit-limit-tokens')} "
          f"tokens/min (remaining {h.get('x-ratelimit-remaining-tokens')})")


if __name__ == "__main__":
    if settings.groq_api_key is None:
        sys.exit("No VOXDOC_GROQ_API_KEY in backend/.env (copy .env.example and fill it in)")
    client = groq.Groq(api_key=settings.groq_api_key.get_secret_value(), timeout=30, max_retries=1)
    for model, max_tokens in [(settings.groq_summary_model, 1200),
                              (settings.groq_summary_model, 40),  # what does running out look like?
                              (settings.groq_qa_model, 1200)]:  # Day 13's model is available too?
        print(f"{model}, max_completion_tokens={max_tokens}:")
        call(client, model, max_tokens)
