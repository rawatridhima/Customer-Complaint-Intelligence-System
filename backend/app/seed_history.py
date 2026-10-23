"""Synthetic complaint history for the analytics dashboard demo.

`make seed` adds a handful of complaints, all submitted today, which leaves
the volume chart as a single point. This adds about three months of
history so the charts, KPIs and emerging-issue detection have something to
show:

  - complaints spread over the last 90 days, more on weekdays
  - older ones mostly resolved, with realistic resolution times
  - a debt-collection surge in the last 7 days, which FR-34 should flag
  - a few agent category corrections, for the model-health panel

Everything is marked: customer_ref starts with DEMO-, channel is "demo".
No LLM is called and nothing is sent to the worker, so it costs no quota.

    make seed-history            # add (refuses if demo history exists)
    make seed-history-clear      # remove it again
"""

import argparse
import random
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from app.core.database import get_session_factory
from app.models.complaint import Complaint
from app.models.enums import AnalysisStatus, Category, ComplaintStatus, Priority, Sentiment
from app.models.feedback import Feedback
from app.models.prediction import Prediction
from app.repositories.user_repo import UserRepository
from app.seed import seed_users
from app.services.priority_service import PriorityService
from app.services.redaction_service import RedactionService

DEMO_PREFIX = "DEMO-"
DAYS = 90
MODEL_VERSION = "distilbert-v1-512"

# Relative daily volume per category (CFPB-like mix).
CATEGORY_WEIGHT = {
    Category.CREDIT_REPORT_DISPUTE: 0.27,
    Category.DEBT_COLLECTION: 0.20,
    Category.CARDS_AND_ACCOUNTS: 0.18,
    Category.MORTGAGE: 0.15,
    Category.CONSUMER_LOANS: 0.12,
    Category.REPORT_MISUSE: 0.08,
}

TEMPLATES: dict[Category, list[str]] = {
    Category.CREDIT_REPORT_DISPUTE: [
        "My credit report shows a {item} that is not mine. I disputed it {n} weeks ago and it is still there.",
        "The balance reported on my {item} is wrong. I paid it down but the bureau still shows the old amount.",
        "A late payment from {n} months ago appears on my report even though I paid on time and have the bank statement.",
        "I asked for an inaccurate {item} to be corrected and received a letter saying it was verified without any explanation.",
    ],
    Category.REPORT_MISUSE: [
        "There is a hard inquiry on my report from a lender I never applied to. I did not authorize anyone to check my credit.",
        "Someone opened a {item} in my name. I never applied for it and I think my identity has been stolen.",
        "A company pulled my credit report without permission while I was only asking for a quote.",
    ],
    Category.DEBT_COLLECTION: [
        "A collection agency keeps calling me about a debt I already paid in full {n} months ago.",
        "I am being contacted about a {item} debt that is not mine. They will not send me any proof of the debt.",
        "The collector called my workplace {n} times this week after I asked them to contact me only in writing.",
        "A debt collector threatened legal action and added fees I never agreed to on an old {item} balance.",
    ],
    Category.CARDS_AND_ACCOUNTS: [
        "There is a charge on my credit card that I do not recognise and the bank has not refunded it after {n} weeks.",
        "My checking account was charged an overdraft fee even though I had enough money when the payment cleared.",
        "My account was frozen without any notice and I cannot access my salary for {n} days.",
        "I was charged twice for the same purchase on my {item} and the dispute was closed without a decision.",
    ],
    Category.MORTGAGE: [
        "My mortgage escrow payment went up because of a shortage I do not understand and nobody explains the calculation.",
        "The servicer applied my mortgage payment late and charged a late fee although I paid {n} days early.",
        "I applied for a loan modification and have sent the same documents {n} times. They keep losing them.",
        "My home insurance claim check is being held by the mortgage company and the repairs cannot start.",
    ],
    Category.CONSUMER_LOANS: [
        "My student loan servicer reported my payments as late while I was enrolled in an income-driven plan.",
        "The vehicle loan payment is higher than the amount in the contract I signed and they will not correct it.",
        "My personal loan was sold to a new company that doubled the interest rate without any notice.",
        "My car was repossessed while I was on an agreed payment arrangement with the lender.",
    ],
}
ITEMS = ["credit card", "store card", "auto loan", "personal loan", "collection account", "medical bill"]
ANGRY_TAILS = [
    " This is fraud, it must be fixed immediately and I am contacting a lawyer.",
    " This is unacceptable and I want it fixed immediately.",
    " I am contacting a lawyer if this is not resolved.",
    " This is the third time I am writing and I am still waiting.",
    "",
    "",
    "",
]


def _text(rng: random.Random, category: Category) -> str:
    template = rng.choice(TEMPLATES[category])
    return template.format(item=rng.choice(ITEMS), n=rng.randint(2, 9)) + rng.choice(ANGRY_TAILS)


def _confidence(rng: random.Random) -> float:
    # Most predictions are confident; about one in five falls under 0.95,
    # matching the test-set coverage in the README (78.5% auto-labelled).
    return round(min(0.999, 1 - rng.betavariate(1, 30)), 3)


def _sentiment(rng: random.Random, text: str) -> tuple[Sentiment, float]:
    if "lawyer" in text or "unacceptable" in text or "third time" in text or "fraud" in text:
        return Sentiment.NEGATIVE, round(rng.uniform(0.80, 0.97), 3)
    roll = rng.random()
    if roll < 0.68:
        return Sentiment.NEGATIVE, round(rng.uniform(0.45, 0.90), 3)
    if roll < 0.97:
        return Sentiment.NEUTRAL, round(rng.uniform(0.50, 0.85), 3)
    return Sentiment.POSITIVE, round(rng.uniform(0.50, 0.80), 3)


def _daily_volume(rng: random.Random, day: datetime) -> int:
    base = 7 if day.weekday() < 5 else 3
    return max(0, base + rng.randint(-2, 3))


def add_history(seed: int = 7) -> int:
    rng = random.Random(seed)
    db = get_session_factory()()
    try:
        if db.execute(select(func.count()).select_from(Complaint)
                      .where(Complaint.customer_ref.like(f"{DEMO_PREFIX}%"))).scalar_one():
            print("Demo history already exists. Run `make seed-history-clear` first.")
            return 0

        seed_users(db)
        agent = UserRepository(db).get_by_username("agent")
        redactor = RedactionService()
        priority = PriorityService()
        now = datetime.now(UTC)
        categories = list(CATEGORY_WEIGHT)
        weights = list(CATEGORY_WEIGHT.values())
        created = 0

        for days_ago in range(DAYS, -1, -1):
            day = (now - timedelta(days=days_ago)).replace(hour=0, minute=0, second=0, microsecond=0)
            for _ in range(_daily_volume(rng, day)):
                category = rng.choices(categories, weights)[0]
                created += _add_one(db, rng, redactor, priority, agent, category, day, days_ago, now)
            # FR-34 demo: debt collection surges in the last week.
            if days_ago < 7:
                for _ in range(rng.randint(4, 6)):
                    created += _add_one(db, rng, redactor, priority, agent,
                                        Category.DEBT_COLLECTION, day, days_ago, now)
        db.commit()
        print(f"Added {created} demo complaints over the last {DAYS} days.")
        return created
    finally:
        db.close()


def _add_one(db, rng, redactor, priority, agent, category, day, days_ago, now) -> int:
    submitted = day + timedelta(minutes=rng.randint(8 * 60, 20 * 60))
    if submitted > now:
        submitted = now - timedelta(minutes=rng.randint(5, 120))
    text = _text(rng, category)
    complaint = Complaint(
        customer_ref=f"{DEMO_PREFIX}{rng.randint(1000, 9999)}",
        raw_text=text,
        redacted_text=redactor.redact(text),
        text_hash=redactor.hash_text(f"{text}|{submitted.isoformat()}"),  # not duplicates
        channel="demo",
        submitted_at=submitted,
        analysis_status=AnalysisStatus.COMPLETED,
    )

    # Status by age: older complaints are mostly resolved.
    roll = rng.random()
    if days_ago > 14:
        status = ComplaintStatus.RESOLVED if roll < 0.9 else ComplaintStatus.ESCALATED
    elif days_ago > 3:
        status = (ComplaintStatus.RESOLVED if roll < 0.55 else
                  ComplaintStatus.AWAITING_CUSTOMER if roll < 0.75 else ComplaintStatus.IN_REVIEW)
    else:
        status = ComplaintStatus.IN_REVIEW if roll < 0.6 else ComplaintStatus.AWAITING_CUSTOMER
    complaint.status = status
    if status is ComplaintStatus.RESOLVED:
        complaint.resolved_at = min(now, submitted + timedelta(hours=rng.uniform(3, 96)))
    db.add(complaint)
    db.flush()

    sentiment, sentiment_score = _sentiment(rng, text)
    confidence = _confidence(rng)
    result = priority.compute(text=complaint.redacted_text, category=category,
                              sentiment_label=sentiment, sentiment_score=sentiment_score,
                              repeat_count=1 if rng.random() < 0.1 else 0)
    if result.bucket is Priority.P0 and status is ComplaintStatus.NEW:
        complaint.status = ComplaintStatus.IN_REVIEW  # keep the live P0 banner for real ones

    prediction = Prediction(
        complaint_id=complaint.complaint_id, category=category,
        category_confidence=confidence, sentiment_label=sentiment,
        sentiment_score=sentiment_score, priority_score=result.score,
        priority_bucket=result.bucket, priority_breakdown=result.breakdown,
        needs_review=confidence < 0.95, model_version=MODEL_VERSION,
        inference_ms=rng.randint(30, 140),
    )
    # A few low-confidence predictions were wrong and corrected by an agent.
    # Below the threshold the model is wrong ~40% of the time (README), and
    # agents catch most of those.
    if agent is not None and confidence < 0.95 and rng.random() < 0.35:
        wrong = rng.choice([c for c in Category if c is not category])
        prediction.original_category = wrong
        prediction.overridden_by = agent.user_id
        prediction.overridden_at = submitted + timedelta(minutes=rng.randint(10, 300))
        prediction.needs_review = False
        db.add(Feedback(
            complaint_id=complaint.complaint_id, field_corrected="category",
            original_value=wrong.value, corrected_value=category.value,
            corrected_by=agent.user_id, model_version=MODEL_VERSION,
            created_at=prediction.overridden_at,
        ))
    db.add(prediction)
    return 1


def clear_history() -> int:
    db = get_session_factory()()
    try:
        result = db.execute(delete(Complaint).where(Complaint.customer_ref.like(f"{DEMO_PREFIX}%")))
        db.commit()
        print(f"Removed {result.rowcount} demo complaints.")
        return result.rowcount
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add or remove synthetic demo history.")
    parser.add_argument("--clear", action="store_true", help="remove the demo history")
    args = parser.parse_args()
    sys.exit(0 if (clear_history() if args.clear else add_history()) >= 0 else 1)
