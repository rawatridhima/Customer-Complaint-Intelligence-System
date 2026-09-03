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
