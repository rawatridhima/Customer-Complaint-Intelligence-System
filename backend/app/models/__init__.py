"""Import model modules so SQLAlchemy registers all tables."""

from app.models.audit_log import AuditLog
from app.models.complaint import Complaint
from app.models.feedback import Feedback
from app.models.generated_content import GeneratedContent
from app.models.knowledge_article import KnowledgeArticle
from app.models.prediction import Prediction
from app.models.user import User

__all__ = [
    "AuditLog",
    "Complaint",
    "Feedback",
    "GeneratedContent",
    "KnowledgeArticle",
    "Prediction",
    "User",
]