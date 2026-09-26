from enum import StrEnum


class UserRole(StrEnum):
    AGENT = "agent"
    MANAGER = "manager"
    ADMIN = "admin"


class ComplaintStatus(StrEnum):
    NEW = "new"
    IN_REVIEW = "in_review"
    AWAITING_CUSTOMER = "awaiting_customer"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Category(StrEnum):
    CREDIT_REPORT_DISPUTE = "credit_report_dispute"
    REPORT_MISUSE = "report_misuse"
    DEBT_COLLECTION = "debt_collection"
    CARDS_AND_ACCOUNTS = "cards_and_accounts"
    MORTGAGE = "mortgage"
    CONSUMER_LOANS = "consumer_loans"


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class Priority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


ALLOWED_TRANSITIONS: dict[ComplaintStatus, set[ComplaintStatus]] = {
    ComplaintStatus.NEW: {ComplaintStatus.IN_REVIEW, ComplaintStatus.ESCALATED},
    ComplaintStatus.IN_REVIEW: {
        ComplaintStatus.AWAITING_CUSTOMER,
        ComplaintStatus.RESOLVED,
        ComplaintStatus.ESCALATED,
    },
    ComplaintStatus.AWAITING_CUSTOMER: {
        ComplaintStatus.RESOLVED,
        ComplaintStatus.ESCALATED,
    },
    ComplaintStatus.ESCALATED: {ComplaintStatus.RESOLVED},
    ComplaintStatus.RESOLVED: set(),
}
