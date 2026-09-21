from datetime import date, datetime, time

from gestao_recebiveis.clock import BUSINESS_TZ

STAGES = (-3, 0, 3, 7)
NORMAL_DELAYS = (30, 120, 600, 1800)
DEMO_DELAYS = (1, 2, 4, 8)


def eligible_stages(due_date: date, now: datetime) -> tuple[int, ...]:
    local_now = now.astimezone(BUSINESS_TZ)
    elapsed_days = (local_now.date() - due_date).days
    reached_target_hour = local_now.time() >= time(9)
    return tuple(
        stage
        for stage in STAGES
        if elapsed_days > stage or (elapsed_days == stage and reached_target_hour)
    )


def retry_delay(attempt_number: int, *, demo: bool) -> int:
    delays = DEMO_DELAYS if demo else NORMAL_DELAYS
    return delays[min(max(attempt_number - 1, 0), len(delays) - 1)]
