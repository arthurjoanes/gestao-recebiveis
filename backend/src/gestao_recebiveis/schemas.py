from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginInput(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class PaymentInput(Input):
    idempotency_key: str = Field(min_length=8, max_length=100)
    note: str = Field(default="", max_length=500)


class CancelInput(Input):
    reason: str = Field(min_length=3, max_length=500)


class ClockInput(Input):
    business_now: datetime


class WorkerInput(Input):
    enabled: StrictBool


class ScenarioInput(Input):
    receivable_id: int = Field(gt=0, le=2147483647, strict=True)
    scenario: Literal["success", "transient", "permanent", "response_lost", "always_transient"]
