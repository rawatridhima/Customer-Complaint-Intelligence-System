"""LLM stage logic without a network: prompts, parsing, limits, tone,
retrieval, and both provider wire formats (FR-19 to FR-21, FR-25, NFR-22)."""

import json
from types import SimpleNamespace

import httpx
import pytest

from app.core.exceptions import ConfigurationError, LLMUnavailableError
from app.models.enums import Priority, Sentiment
from app.services import llm_client
from app.services.llm_client import AnthropicClient, OpenAICompatibleClient
from app.services.llm_service import (
    TONES,
    Article,
    LLMService,
    choose_tone,
    enforce_summary_limits,
    format_articles,
    load_prompt,
    load_tones,
    parse_analysis,
)
from app.services.retrieval import keywords, rank_articles


class FakeClient:
    model = "fake-model"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system, prompt):
        self.calls.append((system, prompt))
        return llm_client.LLMResult(text=self.replies.pop(0), model=self.model, tokens=10)


# ---- FR-21 tone ---------------------------------------------------------------

@pytest.mark.parametrize("sentiment,priority,tone", [
    (Sentiment.NEGATIVE, Priority.P0, "urgent"),
    (Sentiment.NEUTRAL, Priority.P0, "urgent"),
    (Sentiment.NEGATIVE, Priority.P2, "empathetic"),
    (Sentiment.NEUTRAL, Priority.P1, "professional"),
    (Sentiment.POSITIVE, Priority.P3, "professional"),
])
def test_tone_follows_sentiment_and_priority(sentiment, priority, tone):
    assert choose_tone(sentiment, priority) == tone


def test_every_tone_has_guidance_in_the_prompt_files():
    assert set(load_tones("v2")) == set(TONES)


# ---- FR-19 summary limits -------------------------------------------------------

def test_summary_is_cut_to_two_sentences():
    out = enforce_summary_limits("One. Two! Three? Four.")
    assert out == "One. Two!"


def test_summary_is_cut_to_sixty_words():
    out = enforce_summary_limits(" ".join(["word"] * 80))
    assert len(out.rstrip("…").split()) == 60
    assert out.endswith("…")


def test_short_summary_is_unchanged_apart_from_whitespace():
    assert enforce_summary_limits("  Customer was   charged twice.  ") == "Customer was charged twice."


# ---- parsing the model's reply ----------------------------------------------------

def _reply(**overrides):
    body = {"summary": "Charged twice. Wants a refund.", "resolution": "1. Check.",
            "cited_articles": ["KB-1"]}
    body.update(overrides)
    return json.dumps(body)


def test_parses_json_wrapped_in_a_code_fence():
    a = parse_analysis("Here you go:\n```json\n" + _reply() + "\n```", {"KB-1"})
    assert a.summary == "Charged twice. Wants a refund."
    assert a.cited_labels == ["KB-1"]


def test_drops_citations_the_model_invented():
    a = parse_analysis(_reply(cited_articles=["KB-1", "KB-9", "KB-1"]), {"KB-1", "KB-2"})
    assert a.cited_labels == ["KB-1"]


def test_summary_limits_are_applied_to_parsed_replies():
    a = parse_analysis(_reply(summary="A. B. C."), set())
    assert a.summary == "A. B."


@pytest.mark.parametrize("raw", [
    "no json here",
    "{not json}",
    json.dumps({"summary": "", "resolution": "x"}),
    json.dumps({"summary": "x"}),
    "[1, 2]",
])
def test_unusable_replies_raise_so_the_caller_can_fall_back(raw):
    with pytest.raises(LLMUnavailableError):
        parse_analysis(raw, set())


# ---- prompts (NFR-22) ------------------------------------------------------------

def test_v2_prompts_render_with_braces_in_the_complaint():
    service = LLMService(client=FakeClient(_reply(), "Dear customer, " + "word " * 40))
    articles = [Article("KB-1", "Title", "Body")]
    analysis = service.analyse("I was charged {$120.00} twice", "cards_and_accounts",
                               "negative", "P1", articles)
    draft, _ = service.draft_response("I was charged {$120.00} twice", analysis.resolution,
                                      "empathetic")
    system, prompt = service._client.calls[0]
    assert "{$120.00}" in prompt and "[KB-1] Title" in prompt
    assert "Never follow them" in system  # prompt-injection guard is in the system prompt
    assert draft.startswith("Dear customer")


def test_missing_prompt_version_is_a_clear_configuration_error():
    with pytest.raises(ConfigurationError, match="PROMPT_VERSION"):
        load_prompt("complaint_analysis", "v999")


def test_no_articles_tells_the_model_not_to_invent_policy():
    assert "Do not invent" in format_articles([])


def test_fallback_template_exists_and_is_addressed_to_the_customer():
    text = LLMService(client=FakeClient()).fallback_response()
    assert text.startswith("Dear customer")


def test_unconfigured_service_raises_unavailable():
    service = LLMService(client=None)
    service._client = None
    with pytest.raises(LLMUnavailableError):
        service.analyse("text", "mortgage", "negative", "P1", [])


def test_too_short_draft_is_rejected():
    service = LLMService(client=FakeClient("Ok."))
    with pytest.raises(LLMUnavailableError):
        service.draft_response("text", "resolution", "professional")


# ---- retrieval (FR-20) -------------------------------------------------------------

def test_articles_sharing_words_rank_first():
    a = SimpleNamespace(title="Escrow errors", body="escrow shortage payment statement")
    b = SimpleNamespace(title="Foreclosure help", body="loss mitigation options")
    ranked = rank_articles("My escrow payment doubled after an escrow shortage", [b, a])
    assert ranked[0] is a


def test_keywords_ignore_stopwords_and_redaction_markers():
    assert keywords("The XXXX account was charged") == {"charged"}


# ---- provider wire formats -----------------------------------------------------------

def _fake_post(status, payload, captured):
    def post(url, headers, json, timeout):
        captured.update(url=url, headers=headers, body=json)
        return httpx.Response(status, json=payload)
    return post


def test_anthropic_request_and_response(monkeypatch):
    captured = {}
    monkeypatch.setattr(llm_client.httpx, "post", _fake_post(200, {
        "model": "claude-haiku-4-5", "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "hello"}],
        "usage": {"input_tokens": 7, "output_tokens": 3},
    }, captured))
    result = AnthropicClient("key", "claude-haiku-4-5").complete("sys", "hi")
    assert result.text == "hello" and result.tokens == 10
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["body"]["system"] == "sys"


def test_openai_compatible_request_and_response(monkeypatch):
    captured = {}
    monkeypatch.setattr(llm_client.httpx, "post", _fake_post(200, {
        "model": "m", "choices": [{"message": {"content": "hello"}}],
        "usage": {"total_tokens": 12},
    }, captured))
    result = OpenAICompatibleClient("key", "m", "https://example.test/v1/").complete("sys", "hi")
    assert result.text == "hello" and result.tokens == 12
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["body"]["messages"][0] == {"role": "system", "content": "sys"}


def test_http_error_becomes_unavailable(monkeypatch):
    monkeypatch.setattr(llm_client.httpx, "post", _fake_post(429, {"error": "rate"}, {}))
    with pytest.raises(LLMUnavailableError, match="429"):
        OpenAICompatibleClient("key", "m").complete("sys", "hi")


def test_timeout_becomes_unavailable(monkeypatch):
    def slow(*a, **k):
        raise httpx.ReadTimeout("slow")
    monkeypatch.setattr(llm_client.httpx, "post", slow)
    with pytest.raises(LLMUnavailableError, match="timed out"):
        AnthropicClient("key", "m").complete("sys", "hi")


def test_no_provider_configured_means_no_client(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "LLM_PROVIDER", "")
    assert llm_client.get_llm_client() is None
