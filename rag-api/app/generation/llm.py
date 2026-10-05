from functools import lru_cache

import anthropic


@lru_cache
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()  # key from ANTHROPIC_API_KEY


def anthropic_call(
    *, model: str, system: str, user: str, schema: dict, effort: str | None = None
) -> dict:
    """One JSON-schema-constrained call. Returns a plain dict so evals can cache it."""
    output_config: dict = {"format": {"type": "json_schema", "schema": schema}}
    if effort:
        output_config["effort"] = effort
    r = _client().messages.create(
        model=model,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config=output_config,
    )
    return {
        "text": next((b.text for b in r.content if b.type == "text"), ""),
        "stop_reason": r.stop_reason,
        "usage": {"input": r.usage.input_tokens, "output": r.usage.output_tokens},
        "model": model,
    }
