"""Versioned stage-event contract. Nullable fields mean unobserved, not zero."""

from typing import Literal, Any
from pydantic import BaseModel, ConfigDict


class StageEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["3.0"]
    run_id: str | None
    model: str | None
    scenario: str
    environment: str
    stage_id: Literal[
        "S01",
        "S02",
        "S03",
        "S04",
        "S05",
        "S06",
        "S07",
        "S08",
        "S09",
        "S10",
        "S11",
        "S12",
        "S13",
    ]
    payment_method: str
    event_type: Literal["stage_transition", "terminal_failure", "observed_error"]
    timestamp: str
    elapsed: float
    previous_status: str
    status: Literal[
        "not_applicable",
        "not_reached",
        "reached",
        "attempted",
        "completed",
        "failed",
        "recovered",
        "handoff_required",
        "safe_abort",
    ]
    action_attempted: str
    action_source: Literal["model", "controller", "browser", "user"]
    model_prediction: Any = None
    validation_result: bool | None
    error_type: str | None
    recovery_attempted: bool
    recovery_outcome: str | None
    screenshot: str | None
    action_trace: int | str | None
