"""Priority weights a manager can change at runtime (FR-17, FR-39).

The defaults come from .env (PRIORITY_W_*). A manager's change is stored in
the app_settings table and wins over the defaults until it is reset. Every
change is audited.
"""

import json
import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import ConfigurationError, ValidationError
from app.models.audit_log import AuditLog
from app.models.user import User
from app.repositories.audit_log_repo import AuditLogRepository
from app.repositories.complaint_repo import ComplaintRepository
from app.repositories.settings_repo import SettingsRepository
from app.repositories.user_repo import UserRepository
from app.services.priority_service import PriorityService, PriorityWeights

WEIGHTS_KEY = "priority_weights"
FACTORS = ("sentiment", "category", "urgency", "repeat")


def weights_to_dict(w: PriorityWeights) -> dict[str, float]:
    return {f: getattr(w, f) for f in FACTORS}


class SettingsService:
    def __init__(self, db: Session) -> None:
        self._settings = SettingsRepository(db)
        self._audit = AuditLogRepository(db)
        self._users = UserRepository(db)
        self._complaints = ComplaintRepository(db)

    # ---- reading ---------------------------------------------------------------

    def priority_weights(self) -> PriorityWeights:
        """The weights in force now: the stored ones, or the .env defaults."""
        row = self._settings.get(WEIGHTS_KEY)
        if row is None:
            return PriorityWeights.from_settings()
        try:
            return PriorityWeights(**{f: float(row.value[f]) for f in FACTORS})
        except (KeyError, TypeError, ValueError, ConfigurationError):
            # A bad stored value must never stop complaints being scored.
            return PriorityWeights.from_settings()

    def priority_weights_view(self) -> dict:
        row = self._settings.get(WEIGHTS_KEY)
        user = self._users.get(row.updated_by) if row and row.updated_by else None
        return {
            "weights": weights_to_dict(self.priority_weights()),
            "defaults": weights_to_dict(PriorityWeights.from_settings()),
            "is_custom": row is not None,
            "updated_by": user.username if user else None,
            "updated_at": row.updated_at if row else None,
        }

    # ---- changing ----------------------------------------------------------------

    def set_priority_weights(
        self, weights: dict[str, float], actor: User, recalculate_open: bool = False
    ) -> tuple[dict, int]:
        """Store new weights. Returns (view, number of complaints re-scored)."""
        try:
            new = PriorityWeights(**{f: round(float(weights[f]), 4) for f in FACTORS})
        except ConfigurationError as exc:
            raise ValidationError(exc.message) from exc
        old = self.priority_weights()
        self._settings.put(WEIGHTS_KEY, weights_to_dict(new), actor.user_id)
        self._record(actor, "priority_weights_changed",
                     {"from": weights_to_dict(old), "to": weights_to_dict(new)})
        rescored = self._rescore_open(new) if recalculate_open else 0
        self._settings.commit()
        return self.priority_weights_view(), rescored

    def reset_priority_weights(self, actor: User, recalculate_open: bool = False) -> tuple[dict, int]:
        old = self.priority_weights()
        self._settings.delete(WEIGHTS_KEY)
        defaults = PriorityWeights.from_settings()
        self._record(actor, "priority_weights_reset",
                     {"from": weights_to_dict(old), "to": weights_to_dict(defaults)})
        rescored = self._rescore_open(defaults) if recalculate_open else 0
        self._settings.commit()
        return self.priority_weights_view(), rescored

    def _rescore_open(self, weights: PriorityWeights) -> int:
        """Apply new weights to every complaint that is not resolved yet, so the
        inbox order reflects them straight away. Resolved complaints keep the
        score they were handled with."""
        priority = PriorityService(weights)
        count = 0
        for complaint in self._complaints.open_with_predictions():
            p = complaint.prediction
            result = priority.compute(
                text=complaint.redacted_text,
                category=p.category,
                sentiment_label=p.sentiment_label,
                sentiment_score=float(p.sentiment_score),
                repeat_count=max(self._complaints.count_prior_complaints(complaint.customer_ref), 0),
            )
            p.priority_score = result.score
            p.priority_bucket = result.bucket
            p.priority_breakdown = result.breakdown
            count += 1
        return count

    def _record(self, actor: User, action: str, details: dict) -> None:
        self._audit.add(AuditLog(
            actor_id=actor.user_id, action=action, entity_type="settings",
            entity_id=None, details=json.dumps(details),
        ))
