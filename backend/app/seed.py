"""Populate the database with sample complaints. Run: make seed

The schema must already exist: the api container runs `alembic upgrade head`
on start, or run `make migrate` yourself.

The samples are written in the style of the CFPB Consumer Complaint
Database the classifier was trained on (financial products, consumer
voice, redaction markers), so the seeded dashboard shows the six real
categories rather than placeholder data.

Coverage is deliberate:
  - all six categories appear at least once
  - CUST-2004 files twice, so the repeat_complaint priority factor fires
  - one complaint carries urgency terms (fraud / legal) for a P0 row
  - one is calm and factual, to show a low-priority row
  - the last entry repeats CUST-2001's text verbatim, to demonstrate
    duplicate detection (FR-05)
"""

from app.core.database import get_session_factory
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.complaint import ComplaintCreate
from app.services.complaint_service import ComplaintService

# Demo accounts, one per role, for local development and the viva demo only.
# For a real deployment create accounts with: python -m app.create_user
DEMO_USERS = [
    ("agent", "agent@example.com", "agent-demo-pass", UserRole.AGENT),
    ("manager", "manager@example.com", "manager-demo-pass", UserRole.MANAGER),
    ("admin", "admin@example.com", "admin-demo-pass", UserRole.ADMIN),
]

_UNAUTHORISED_INQUIRY = (
    "There is a hard inquiry on my Equifax report from a lender I have never "
    "applied to, dated XX/XX/2018. I did not authorize anyone to pull my credit "
    "report and this inquiry has lowered my score. I want it removed."
)

SAMPLES = [
    # report_misuse
    (_UNAUTHORISED_INQUIRY, "CUST-2001"),
    (
        "I received a letter saying I was approved for a store card I never applied "
        "for. Someone is using my information to open accounts. This is identity "
        "fraud and I am contacting a lawyer if it is not resolved immediately.",
        "CUST-2002",
    ),
    # credit_report_dispute
    (
        "I have disputed the same account with Experian three times now. They keep "
        "coming back saying it is verified, but they have never sent me the "
        "origination documents I asked for. The account is not mine.",
        "CUST-2003",
    ),
    (
        "My short sale was completed in 2017 but it is being reported as a "
        "foreclosure on my credit file. This is inaccurate and it is the reason I "
        "was turned down for a car loan last week. Please make them correct it.",
        "CUST-2004",
    ),
    # debt_collection
    (
        "A collection agency has been calling my workplace after I told them twice "
        "in writing to stop. They have added fees to the balance that nobody will "
        "explain and they will not send me validation of the debt.",
        "CUST-2005",
    ),
    (
        "I am being contacted about a debt I already paid off in full last year. I "
        "sent them the receipt and they still refuse to remove it. I have never "
        "owed this company anything since then.",
        "CUST-2006",
    ),
    # mortgage
    (
        "My mortgage servicer is holding the insurance check for my roof repair and "
        "will not release the funds. The roof is still open and they have had the "
        "check for six weeks. Meanwhile they are threatening foreclosure.",
        "CUST-2007",
    ),
    (
        "I applied for a loan modification in XX/XX/2018 and have sent the same "
        "paperwork four times because they keep changing my representative. Each "
        "time I call I am told the file is still under review.",
        "CUST-2008",
    ),
    # cards_and_accounts
    (
        "There were unauthorized charges of {$450.00} on my credit card. I reported "
        "them the same day, but the bank reversed the temporary credit without "
        "telling me and now says I am responsible for the full amount.",
        "CUST-2009",
    ),
    (
        "I would like a copy of my checking account statement for last month. The "
        "online banking site only shows the last 90 days and I need an older one "
        "for my records. Please advise how to request it.",
        "CUST-2010",
    ),
    # consumer_loans
    (
        "My student loan servicer reported my payments as late even though I have "
        "been in deferment since XX/XX/2018. Nobody emailed or called me, and I "
        "only found out when my score dropped.",
        "CUST-2011",
    ),
    (
        "I took a payday loan and was told the terms were six payments of {$120.00}. "
        "The contract that printed had completely different terms that I never "
        "signed, and they are now charging me late fees on top.",
        "CUST-2004",
    ),
    # Exact repeat of the first complaint, same customer: FR-05 duplicate detection.
    (_UNAUTHORISED_INQUIRY, "CUST-2001"),
]


def seed_users(db) -> None:
    """Idempotent: running make seed twice does not duplicate accounts."""
    users = UserRepository(db)
    for username, email, password, role in DEMO_USERS:
        if users.get_by_username(username):
            continue
        users.add(User(
            username=username, email=email,
            password_hash=hash_password(password), role=role,
        ))
        print(f"created user {username:8} password {password:18} role {role.value}")
    users.commit()


def main() -> None:
    db = get_session_factory()()
    seed_users(db)
    service = ComplaintService(db)
    for text, ref in SAMPLES:
        complaint = service.create(ComplaintCreate(text=text, customer_ref=ref))
        marker = " (duplicate)" if complaint.duplicate_of else ""
        print(f"created {complaint.complaint_id}{marker}")
    db.close()


if __name__ == "__main__":
    main()