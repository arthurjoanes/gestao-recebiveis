import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    field_validator,
)


def reject_nul(value: str) -> str:
    if "\x00" in value:
        raise ValueError("O campo não pode conter o caractere NUL.")
    return value


DatabaseText = Annotated[str, AfterValidator(reject_nul)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginInput(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    email: DatabaseText = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class PaymentInput(Input):
    idempotency_key: DatabaseText = Field(min_length=8, max_length=100)
    note: DatabaseText = Field(default="", max_length=500)
    amount_cents: StrictStr | None = Field(
        default=None,
        pattern=r"^[1-9][0-9]{0,18}$",
        description=(
            "Centavos positivos como string canônica, até 9223372036854775807; "
            "omitir quita o saldo restante. null explícito é inválido."
        ),
    )

    @field_validator("amount_cents", mode="before")
    @classmethod
    def strict_positive_cents(cls, value: object) -> str:
        # Check the raw field before Input's whitespace normalization. An explicit
        # null is not the same request as omitting the amount.
        if (
            not isinstance(value, str)
            or re.fullmatch(r"[1-9][0-9]{0,18}", value) is None
            or int(value) > 9223372036854775807
        ):
            raise ValueError("Informe centavos positivos como string, até 9223372036854775807.")
        return value


class CancelInput(Input):
    reason: DatabaseText = Field(min_length=3, max_length=500)


class ClockInput(Input):
    business_now: datetime


class WorkerInput(Input):
    enabled: StrictBool


class ScenarioInput(Input):
    receivable_id: int = Field(gt=0, le=2147483647, strict=True)
    scenario: Literal["success", "transient", "permanent", "response_lost", "always_transient"]
