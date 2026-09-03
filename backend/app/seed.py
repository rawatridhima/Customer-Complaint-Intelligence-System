"""Populate the database with sample complaints. Run: make seed"""

from app.core.database import Base, get_engine, get_session_factory
from app.schemas.complaint import ComplaintCreate
from app.services.complaint_service import ComplaintService

SAMPLES = [
    ("I was charged twice for order 88421 on 12 August and support has not replied in 5 days.", "CUST-1001"),
    ("The parcel was supposed to arrive last Tuesday. Tracking has not updated and nobody answers.", "CUST-1002"),
    ("Product arrived broken. The screen is cracked and the box was damaged. This is unacceptable.", "CUST-1003"),
    ("Refund was promised three weeks ago and I have still not received the money back. Urgent.", "CUST-1004"),
    ("The app crashes every time I try to log in with OTP. Error appears immediately on submit.", "CUST-1005"),
    ("Your agent was extremely rude on the call and hung up on me while I was still speaking.", "CUST-1006"),
    ("Thanks for resolving my issue quickly, the replacement arrived and works great.", "CUST-1007"),
    ("This is the third time I am writing about the same billing error. Considering consumer court.", "CUST-1004"),
]


def main() -> None:
    Base.metadata.create_all(bind=get_engine())
    db = get_session_factory()()
    service = ComplaintService(db)
    for text, ref in SAMPLES:
        complaint = service.create(ComplaintCreate(text=text, customer_ref=ref))
        print(f"created {complaint.complaint_id}")
    db.close()


if __name__ == "__main__":
    main()
