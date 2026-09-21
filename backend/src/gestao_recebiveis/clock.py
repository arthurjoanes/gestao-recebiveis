from datetime import UTC, date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

BUSINESS_TZ = ZoneInfo("America/Sao_Paulo")


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    def __init__(self, instant: datetime):
        self.instant = instant

    def now(self) -> datetime:
        return self.instant


def utcnow() -> datetime:
    return datetime.now(UTC)


def business_now(session: Session) -> datetime:
    from gestao_recebiveis.config import get_settings
    from gestao_recebiveis.models import DemoState

    state = session.get(DemoState, 1)
    if get_settings().demo_mode and state is not None:
        return state.business_now.astimezone(BUSINESS_TZ)
    return utcnow().astimezone(BUSINESS_TZ)


def business_date(session: Session) -> date:
    return business_now(session).date()
