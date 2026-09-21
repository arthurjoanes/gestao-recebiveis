import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from pwdlib import PasswordHash
from sqlalchemy import delete, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from gestao_recebiveis.config import get_settings
from gestao_recebiveis.database import SessionLocal
from gestao_recebiveis.generator import DEFAULT_REFERENCE, encode_csv, generate_rows
from gestao_recebiveis.imports import confirm_batch, create_preview
from gestao_recebiveis.models import Base, DemoState, ImportBatch, Receivable, User
from gestao_recebiveis.receivables import pay

DEMO_PASSWORD = "Recebiveis!2026"


def seed_demo(session: Session) -> dict[str, int]:
    if not get_settings().demo_mode:
        raise ValueError("Seed de contas demo exige DEMO_MODE=true.")
    session.execute(text("SELECT pg_advisory_xact_lock(83471021)"))
    for email, name, role in [
        ("operador@example.com", "Operador de demonstração", "operator"),
        ("leitor@example.com", "Leitor de demonstração", "reader"),
    ]:
        if session.scalar(select(User).where(User.email == email)) is None:
            session.add(
                User(
                    email=email,
                    name=name,
                    role=role,
                    is_demo=True,
                    password_hash=PasswordHash.recommended().hash(DEMO_PASSWORD),
                )
            )
    if session.get(DemoState, 1) is None:
        session.add(
            DemoState(
                id=1,
                business_now=datetime.fromisoformat(f"{DEFAULT_REFERENCE}T10:00:00-03:00"),
                worker_enabled=False,
            )
        )
    session.flush()
    operator = session.scalar(select(User).where(User.email == "operador@example.com"))
    if operator is None or operator.role != "operator":
        raise ValueError("A conta demo existente não é operadora; seed recusado.")
    content = encode_csv(generate_rows())
    content_hash = hashlib.sha256(content).hexdigest()
    batch = session.scalar(
        select(ImportBatch)
        .where(ImportBatch.sha256 == content_hash, ImportBatch.status == "confirmed")
        .order_by(ImportBatch.id)
        .limit(1)
    )
    if batch is None:
        batch = create_preview(session, "portfolio.csv", content, operator.id)
        batch = confirm_batch(session, batch.id, operator.id)
        if batch.status != "confirmed":
            raise ValueError(f"Seed rejeitado: {json.dumps(batch.report, ensure_ascii=False)}")
    paid = 0
    for index in range(5, 241, 5):
        external_id = f"TIT-{index:04d}"
        receivable = session.scalar(
            select(Receivable).where(
                Receivable.source_system == "erp_ficticio_v1",
                Receivable.external_receivable_id == external_id,
            )
        )
        if receivable is None:
            raise ValueError(f"Título {external_id} ausente após seed.")
        # Não altera títulos que o operador cancelou depois do primeiro seed.
        if receivable.status == "canceled":
            continue
        pay(
            session,
            receivable.id,
            f"seed-v1-{external_id}",
            "Pagamento fictício do seed",
            operator.id,
        )
        paid += 1
    return {"customers": 60, "receivables": 240, "seed_payments": paid, "batch_id": batch.id}


def reset_demo(session: Session, email: str, password: str, confirm_database: str) -> None:
    settings = get_settings()
    target = make_url(settings.database_url)
    if (
        not settings.demo_mode
        or target.host != "db"
        or target.database != "gestao_recebiveis"
        or confirm_database != "gestao_recebiveis"
    ):
        raise ValueError("Reset permitido apenas no banco local gestao_recebiveis, em DEMO_MODE.")
    operator = session.scalar(select(User).where(User.email == email))
    if (
        operator is None
        or operator.role != "operator"
        or not PasswordHash.recommended().verify(password, operator.password_hash)
    ):
        raise ValueError("Reset exige credenciais válidas de operador.")
    session.execute(text("SELECT pg_advisory_xact_lock(83471021)"))
    # Limpa somente as tabelas deste aplicativo.
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(delete(table))
    session.flush()
    session.expunge_all()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed e reset do ambiente demo.")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--email", default="")
    parser.add_argument("--confirm-database", default="")
    parser.add_argument("--manifest", type=Path, default=Path("/data/generated/manifest.json"))
    args = parser.parse_args()
    if not get_settings().demo_mode:
        raise SystemExit("DEMO_MODE precisa estar habilitado para seed/reset.")
    if args.manifest.exists():
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        expected = hashlib.sha256(encode_csv(generate_rows())).hexdigest()
        if manifest.get("sha256") != expected:
            raise SystemExit("Manifesto não corresponde ao gerador padrão; seed recusado.")
    with SessionLocal.begin() as session:
        if args.reset:
            reset_demo(session, args.email, sys.stdin.read().rstrip("\r\n"), args.confirm_database)
        result = seed_demo(session)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
