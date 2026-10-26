"""LLM provider clients. The only code that talks to an LLM over the network.

Two wire formats cover almost every provider:
  - AnthropicClient: the Claude Messages API
  - OpenAICompatibleClient: the /chat/completions format, which OpenAI,
    Gemini, Groq, OpenRouter and Ollama all accept

Both use httpx directly rather than a vendor SDK, so switching provider is a
.env change and adds no dependency. Every failure (network error, timeout,
non-2xx response, unexpected body) is raised as LLMUnavailableError, which the
caller turns into the template fallback (FR-25).
"""

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.exceptions import LLMRateLimitedError, LLMUnavailableError


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    tokens: int | None


class LLMClient(Protocol):
    model: str

    def complete(self, system: str, prompt: str) -> LLMResult: ...


def _post(url: str, headers: dict, body: dict) -> dict:
    try:
        resp = httpx.post(url, headers=headers, json=body, timeout=settings.LLM_TIMEOUT_SECONDS)
    except httpx.TimeoutException as exc:
        raise LLMUnavailableError(
            f"LLM timed out after {settings.LLM_TIMEOUT_SECONDS}s") from exc
    except httpx.HTTPError as exc:
        raise LLMUnavailableError(f"Could not reach the LLM: {exc.__class__.__name__}") from exc

    if resp.status_code == 429:
        body = resp.text
        daily = "perday" in body.lower().replace(" ", "").replace("_", "")
        try:
            retry_after = int(resp.headers.get("retry-after", "60"))
        except ValueError:
            retry_after = 60
        raise LLMRateLimitedError(
            "LLM daily quota used up (HTTP 429)" if daily
            else "LLM rate limit reached (HTTP 429)",
            retry_after=retry_after, daily=daily,
        )
    if resp.status_code >= 400:
        # Never include the request (it holds the complaint) in the message.
        raise LLMUnavailableError(f"LLM returned HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        return resp.json()
    except ValueError as exc:
        raise LLMUnavailableError("LLM returned a non-JSON response") from exc


class AnthropicClient:
    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str) -> None:
        self._key = api_key
        self.model = model

    def complete(self, system: str, prompt: str) -> LLMResult:
        data = _post(
            self.URL,
            headers={
                "x-api-key": self._key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            body={
                "model": self.model,
                "max_tokens": settings.LLM_MAX_TOKENS,
                "temperature": 0.2,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        try:
            text = "".join(b["text"] for b in data["content"] if b.get("type") == "text")
            usage = data.get("usage") or {}
            tokens = (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0)
        except (KeyError, TypeError) as exc:
            raise LLMUnavailableError("Unexpected response shape from the Claude API") from exc
        if data.get("stop_reason") == "refusal":
            raise LLMUnavailableError("The model declined to answer")
        return LLMResult(text=text, model=data.get("model", self.model), tokens=tokens or None)


class OpenAICompatibleClient:
    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(self, api_key: str, model: str, base_url: str = "") -> None:
        self._key = api_key
        self.model = model
        self._url = (base_url or self.DEFAULT_BASE_URL).rstrip("/") + "/chat/completions"

    def complete(self, system: str, prompt: str) -> LLMResult:
        data = _post(
            self._url,
            headers={"Authorization": f"Bearer {self._key}"},
            body={
                "model": self.model,
                "max_tokens": settings.LLM_MAX_TOKENS,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        try:
            text = data["choices"][0]["message"]["content"] or ""
            tokens = (data.get("usage") or {}).get("total_tokens")
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailableError("Unexpected response shape from the LLM API") from exc
        return LLMResult(text=text, model=data.get("model", self.model), tokens=tokens)


def get_llm_client() -> LLMClient | None:
    """The configured client, or None when no LLM is set up.

    None is a normal state, not an error: the app runs, and every complaint
    gets the template response (FR-25, NFR-07).
    """
    provider = settings.LLM_PROVIDER.strip().lower()
    key = settings.LLM_API_KEY.get_secret_value()
    if not provider or not settings.LLM_MODEL:
        return None
    if provider == "anthropic":
        return AnthropicClient(key, settings.LLM_MODEL) if key else None
    if provider == "openai":
        return OpenAICompatibleClient(key, settings.LLM_MODEL, settings.LLM_BASE_URL)
    raise LLMUnavailableError(
        f"Unknown LLM_PROVIDER '{settings.LLM_PROVIDER}'. Use 'anthropic' or 'openai'.")
