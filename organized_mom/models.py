from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Record(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    event_id: str = Field(min_length=1, max_length=120)
    source: str
    child: str | None = None
    title: str = Field(min_length=1, max_length=250)
    text: str = Field(max_length=12000)
    start: datetime
    end: datetime
    location: str = Field(min_length=1, max_length=250)
    retrieved_at: datetime
    revision: int = Field(default=1, ge=1)
    status: Literal["current", "superseded", "cancelled", "pending_login", "check_failed"] = "current"
    kind: Literal["practice", "tournament", "class", "school", "study", "milestone"] = "class"
    group: bool = False
    makeup_allowed: bool = False
    makeup_start: datetime | None = None
    makeup_end: datetime | None = None
    partial_allowed: bool = False
    driver: str | None = None
    confidence: float = Field(default=1, ge=0, le=1)
    preparation: list[str] = Field(default_factory=list)
    deadline: datetime | None = None
    sensitive: bool = False

    @model_validator(mode="after")
    def valid_times(self):
        for value in (
            self.start,
            self.end,
            self.retrieved_at,
            self.makeup_start,
            self.makeup_end,
            self.deadline,
        ):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError("Dates require an explicit UTC offset.")
        if self.end <= self.start:
            raise ValueError("Event end must follow start.")
        if bool(self.makeup_start) != bool(self.makeup_end):
            raise ValueError("Provide both make-up times.")
        if self.makeup_start and self.makeup_end <= self.makeup_start:
            raise ValueError("Make-up end must follow start.")
        return self


class Ask(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    child: str | None = None
    date: str | None = None


class Feedback(BaseModel):
    status: Literal["acknowledged", "completed", "snoozed", "incorrect", "rescheduled"]
    minutes: int = Field(default=60, ge=1, le=10080)


class Approval(BaseModel):
    action_id: str
    confirmation: Literal["I approve this exact action"]


class Consent(BaseModel):
    enabled: bool
    confirmation: str = ""
