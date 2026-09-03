from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.complaint_service import ComplaintService


def get_complaint_service(db: Session = Depends(get_db)) -> Iterator[ComplaintService]:
    yield ComplaintService(db)
