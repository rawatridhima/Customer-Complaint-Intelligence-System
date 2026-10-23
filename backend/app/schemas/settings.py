from datetime import datetime

from pydantic import BaseModel, Field


class PriorityWeightsIn(BaseModel):
    """FR-17. Each weight is between 0 and 1 and the four must add up to 1."""

    sentiment: float = Field(ge=0, le=1)
    category: float = Field(ge=0, le=1)
    urgency: float = Field(ge=0, le=1)
    repeat: float = Field(ge=0, le=1)


class PriorityWeightsUpdate(BaseModel):
    weights: PriorityWeightsIn
    recalculate_open: bool = Field(
        default=False,
        description="Also re-score every complaint that is not resolved yet.")


class PriorityWeightsOut(BaseModel):
    weights: dict[str, float]
    defaults: dict[str, float]
    is_custom: bool
    updated_by: str | None = None
    updated_at: datetime | None = None
    rescored: int = 0
