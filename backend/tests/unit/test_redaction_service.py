import pytest

from app.services.redaction_service import RedactionService


def test_redacts_email():
    out = RedactionService().redact("Contact me at foo.bar@example.com please")
    assert "foo.bar@example.com" not in out
    assert "<email>" in out


def test_redacts_phone():
    out = RedactionService().redact("Call me on 9876543210 today")
    assert "9876543210" not in out


def test_redacts_long_account_number():
    out = RedactionService().redact("My card 4111111111111111 was charged")
    assert "4111111111111111" not in out


def test_hash_ignores_case_and_whitespace():
    svc = RedactionService()
    assert svc.hash_text("Hello   World") == svc.hash_text("hello world")


def test_hash_differs_for_different_text():
    svc = RedactionService()
    assert svc.hash_text("one") != svc.hash_text("two")


@pytest.mark.parametrize("text", [
    "call me on 555-123-4567 today",
    "call me on (555) 123-4567 today",
    "call me on 555.123.4567 today",
    "call me on +1 555 123 4567 today",
    "call me on +91 98765 43210 today",
])
def test_redacts_phone_numbers_with_separators(text):
    out = RedactionService().redact(text)
    assert "<phone>" in out
    assert not any(ch.isdigit() for ch in out.replace("<phone>", ""))


@pytest.mark.parametrize("text", [
    "card 4111 1111 1111 1111 was charged",
    "card 4111-1111-1111-1111 was charged",
])
def test_redacts_grouped_card_numbers(text):
    out = RedactionService().redact(text)
    assert "<account>" in out and "4111" not in out


@pytest.mark.parametrize("text", [
    "charged {$1,250.00} on 09/30/2026",
    "since 2019-04-01 I have paid 3 times",
    "reference XX/XX/2018 and loan of $12,000",
    "I called 3 times in 2 weeks",
])
def test_leaves_dates_amounts_and_small_numbers_alone(text):
    assert RedactionService().redact(text) == text
