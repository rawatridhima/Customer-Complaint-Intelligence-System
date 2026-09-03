from app.models.enums import ALLOWED_TRANSITIONS, ComplaintStatus


def test_new_can_move_to_in_review():
    assert ComplaintStatus.IN_REVIEW in ALLOWED_TRANSITIONS[ComplaintStatus.NEW]


def test_resolved_is_terminal():
    assert ALLOWED_TRANSITIONS[ComplaintStatus.RESOLVED] == set()


def test_cannot_reopen_resolved():
    assert ComplaintStatus.NEW not in ALLOWED_TRANSITIONS[ComplaintStatus.RESOLVED]


def test_every_status_has_an_entry():
    assert set(ALLOWED_TRANSITIONS) == set(ComplaintStatus)
