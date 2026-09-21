from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from gestao_recebiveis.clock import Clock, SystemClock
from gestao_recebiveis.models import Attempt, Delivery, ProviderResult


@dataclass(frozen=True)
class SendResult:
    outcome: str
    error: str | None = None


class ResponseLost(Exception):
    """O chamador não conhece o resultado; deve repetir a mesma tentativa."""


class MessageProvider(Protocol):
    def send(self, attempt_id: int) -> SendResult: ...


class FakeProvider:
    def __init__(self, session_factory: sessionmaker[Session], clock: Clock | None = None):
        self.session_factory = session_factory
        self.clock = clock or SystemClock()

    def send(self, attempt_id: int) -> SendResult:
        lose_response = False
        with self.session_factory.begin() as session:
            attempt = session.get(Attempt, attempt_id)
            if attempt is None:
                raise ValueError("Tentativa autorizada não encontrada.")
            # Serializa somente o simulador. Não bloqueia título/job nem cruza a
            # ordem de locks usada pela baixa e pela finalização do worker.
            session.execute(
                text("SELECT pg_advisory_xact_lock(:namespace, :reminder_id)"),
                {"namespace": 1128678999, "reminder_id": attempt.reminder_id},
            )
            stored = session.get(ProviderResult, attempt_id)
            if stored is not None:
                return SendResult(stored.outcome, stored.error)

            payload = attempt.payload
            existing = session.scalar(
                select(Delivery).where(Delivery.idempotency_key == payload["idempotency_key"])
            )
            scenario = str(payload["scenario"])
            if existing is not None:
                result = SendResult("success")
            elif scenario == "permanent":
                result = SendResult("permanent", "Destinatário recusado pelo provedor simulado.")
            elif scenario == "always_transient" or (
                scenario == "transient" and attempt.number == 1
            ):
                result = SendResult("transient", "Provedor simulado temporariamente indisponível.")
            else:
                result = SendResult("success")
                session.add(
                    Delivery(
                        reminder_id=attempt.reminder_id,
                        idempotency_key=str(payload["idempotency_key"]),
                        accepted_at=self.clock.now(),
                        message=str(payload["message"]),
                    )
                )
                lose_response = scenario == "response_lost"
            session.add(
                ProviderResult(
                    attempt_id=attempt_id,
                    outcome=result.outcome,
                    error=result.error,
                    created_at=self.clock.now(),
                )
            )
        # A falha acontece depois do COMMIT da aceitação, inclusive após restart.
        if lose_response:
            raise ResponseLost("Aceitação possível; resposta do provedor não recebida.")
        return result
