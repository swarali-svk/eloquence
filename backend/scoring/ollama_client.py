"""Model client for Eloquence scoring.

Dispatches JSON chat completions to either a local Ollama server or Groq's
fast OpenAI-compatible cloud API, selected by config.PROVIDER. Both return a
parsed JSON dict so the scoring pipeline is provider-agnostic.
"""

import json
import re
import requests

from config import (
    PROVIDER, OLLAMA_HOST, OLLAMA_MODEL,
    GROQ_HOST, GROQ_MODEL, GROQ_API_KEY,
)


class OllamaError(RuntimeError):
    """Raised on any provider failure (kept name for existing callers)."""


_warned_fallback = False


def chat_json(system: str, user: str, temperature: float = 0.2,
              num_predict: int = 320) -> dict:
    """Return a parsed JSON dict from the configured provider.

    `num_predict` caps generated tokens (outputs are short JSON). When PROVIDER
    is "groq" the fast cloud path is tried first; on any failure (missing/invalid
    key, rate limit, network, unparseable output) it transparently falls back to
    local Ollama so scoring still works.
    """
    if PROVIDER == "groq":
        try:
            return _parse_json(_groq(system, user, temperature, num_predict))
        except OllamaError as e:
            global _warned_fallback
            if not _warned_fallback:
                print(f"[eloquence] Groq unavailable ({e}); falling back to Ollama.")
                _warned_fallback = True
            return _parse_json(_ollama(system, user, temperature, num_predict))
    return _parse_json(_ollama(system, user, temperature, num_predict))


def _ollama(system: str, user: str, temperature: float, num_predict: int) -> str:
    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "format": "json",
                "stream": False,
                "keep_alive": "10m",
                "options": {"temperature": temperature, "num_predict": num_predict},
            },
            timeout=600,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise OllamaError(f"Ollama request failed: {e}") from e
    body = json.loads(resp.content.decode("utf-8"))
    return body.get("message", {}).get("content", "").strip()


def _groq(system: str, user: str, temperature: float, num_predict: int) -> str:
    if not GROQ_API_KEY:
        raise OllamaError("GROQ_API_KEY is not set but provider is 'groq'.")
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": temperature,
        # Reasoning models spend tokens thinking before emitting JSON, so give
        # generous headroom to avoid empty/invalid JSON (json_validate_failed).
        "max_tokens": max(num_predict + 700, 1024),
    }
    if "gpt-oss" in GROQ_MODEL:
        payload["reasoning_effort"] = "low"
    try:
        resp = requests.post(
            f"{GROQ_HOST}/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json=payload,
            timeout=90,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        detail = ""
        if e.response is not None:
            detail = f" — {e.response.text[:200]}"
        raise OllamaError(f"Groq request failed: {e}{detail}") from e
    body = json.loads(resp.content.decode("utf-8"))
    return body["choices"][0]["message"]["content"].strip()


def _parse_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    raise OllamaError(f"Could not parse JSON from model output: {text[:300]}")
