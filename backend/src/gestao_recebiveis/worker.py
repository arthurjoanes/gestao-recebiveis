import logging
import signal
from threading import Event, Thread
from time import monotonic
from types import FrameType

from sqlalchemy.orm import Session, sessionmaker

from gestao_recebiveis.clock import Clock, SystemClock
from gestao_recebiveis.config import get_settings
from gestao_recebiveis.database import SessionLocal
from gestao_recebiveis.models import DemoState
from gestao_recebiveis.reminders.provider import FakeProvider, MessageProvider, ResponseLost, SendResult
from gestao_recebiveis.reminders.service import Claim, authorize, claim, finish, renew, schedule

logger = logging.getLogger("gestao_recebiveis.worker")


class LeaseHeartbeat:
    def __init__(self, factory: sessionmaker[Session], possession: Claim, clock: Clock) -> None:
        self.factory = factory
        self.possession = possession
        self.clock = clock
        self.stopped = Event()
        self.thread = Thread(target=self._run, daemon=True, name="gestao_recebiveis-lease")

    def _run(self) -> None:
        while not self.stopped.wait(get_settings().heartbeat_seconds):
            try:
                with self.factory.begin() as session:
                    valid = renew(session, self.possession, clock=self.clock)
                if not valid:
                    logger.warning("lease_lost reminder_id=%s", self.possession.reminder_id)
                    return
            except Exception as exc:
                logger.error(
                    "lease_renewal_failed reminder_id=%s error_type=%s",
                    self.possession.reminder_id,
                    type(exc).__name__,
                )
                return

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stopped.set()
        self.thread.join(timeout=5)


def run_once(
    session_factory: sessionmaker[Session] = SessionLocal,
    *,
    clock: Clock | None = None,
    provider: MessageProvider | None = None,
    schedule_pending: bool = True,
) -> bool:
    infra_clock = clock or SystemClock()
    with session_factory.begin() as session:
        enabled = True
        if get_settings().demo_mode:
            demo = session.get(DemoState, 1)
            if demo is None:
                return False
            enabled = demo.worker_enabled
        scheduled = schedule(session, clock=infra_clock) if schedule_pending else 0
    if scheduled:
        logger.info("scheduled count=%s", scheduled)
    if not enabled:
        return False

    with session_factory.begin() as session:
        possession = claim(session, clock=infra_clock)
    if possession is None:
        return False
    with session_factory.begin() as session:
        attempt = authorize(session, possession, clock=infra_clock)
        attempt_id = attempt.id if attempt is not None else None
    if attempt_id is None:
        return True

    heartbeat = LeaseHeartbeat(session_factory, possession, infra_clock)
    heartbeat.start()
    try:
        sender = provider or FakeProvider(session_factory, infra_clock)
        try:
            outcome = sender.send(attempt_id)
        except ResponseLost as exc:
            outcome = SendResult("unknown", str(exc))
        except Exception as exc:
            logger.error(
                "provider_result_unknown attempt_id=%s error_type=%s",
                attempt_id,
                type(exc).__name__,
            )
            outcome = SendResult("unknown", "Provedor interrompido. Consultar a tentativa.")
        with session_factory.begin() as session:
            accepted = finish(session, possession, attempt_id, outcome, clock=infra_clock)
        logger.info(
            "attempt_result reminder_id=%s attempt_id=%s outcome=%s owner_accepted=%s",
            possession.reminder_id,
            attempt_id,
            outcome.outcome,
            accepted,
        )
    finally:
        heartbeat.stop()
    return True


def main() -> None:
    settings = get_settings()
    settings.validate_runtime()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stopped = Event()

    def shutdown(signum: int, frame: FrameType | None) -> None:
        logger.info("worker_shutdown signal=%s", signum)
        stopped.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    logger.info("worker_started demo=%s", settings.demo_mode)
    next_schedule_at = 0.0
    while not stopped.is_set():
        iteration_started = monotonic()
        schedule_pending = iteration_started >= next_schedule_at
        if schedule_pending:
            # Drenar N jobs não deve repetir N vezes a varredura da carteira.
            # Monotonic mantém esse intervalo independente do relógio demo.
            next_schedule_at = iteration_started + settings.worker_poll_seconds
        try:
            worked = run_once(schedule_pending=schedule_pending)
        except Exception as exc:
            logger.error("worker_iteration_failed error_type=%s", type(exc).__name__)
            worked = False
        if not worked:
            stopped.wait(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
