import hashlib
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from gestao_recebiveis.audit import record
from gestao_recebiveis.errors import DomainError
from gestao_recebiveis.import_csv import MAX_BYTES, parse
from gestao_recebiveis.models import Customer, ImportBatch, ImportLine, Receivable


def analyze(
    session: Session, content: bytes, *, write: bool = False, actor_id: int | None = None
) -> dict[str, Any]:
    rows, errors = parse(content)
    unique = {row.title_key: row for row in rows}
    customers = {row.customer_key: row for row in rows}
    customer_ids: dict[tuple[str, str], int] = {}
    customer_conflicts: set[tuple[str, str]] = set()
    statuses: dict[tuple[str, str], str] = {}
    if not errors:
        for key, row in sorted(customers.items()):
            stmt = select(Customer).where(
                Customer.source_system == key[0], Customer.external_customer_id == key[1]
            )
            if write:
                session.execute(
                    insert(Customer)
                    .values(
                        source_system=key[0],
                        external_customer_id=key[1],
                        name=row.customer_name,
                        email=row.customer_email,
                    )
                    .on_conflict_do_nothing()
                )
                stmt = stmt.with_for_update()
            customer = session.scalar(stmt)
            if customer:
                customer_ids[key] = customer.id
                if (customer.name, customer.email) != (row.customer_name, row.customer_email):
                    customer_conflicts.add(key)
        for key, row in sorted(unique.items()):
            stmt_title = select(Receivable).where(
                Receivable.source_system == key[0], Receivable.external_receivable_id == key[1]
            )
            created_id = None
            if write and row.customer_key not in customer_conflicts:
                created_id = session.scalar(
                    insert(Receivable)
                    .values(
                        source_system=key[0],
                        external_receivable_id=key[1],
                        customer_id=customer_ids[row.customer_key],
                        description=row.description,
                        amount_cents=row.amount_cents,
                        due_date=row.due_date,
                        status="open",
                        scenario="success",
                    )
                    .on_conflict_do_nothing()
                    .returning(Receivable.id)
                )
                stmt_title = stmt_title.with_for_update()
            title = session.scalar(stmt_title)
            if row.customer_key in customer_conflicts:
                statuses[key] = "conflict"
            elif title and (
                title.customer_id,
                title.description,
                title.amount_cents,
                title.due_date,
            ) != (
                customer_ids.get(row.customer_key),
                row.description,
                row.amount_cents,
                row.due_date,
            ):
                statuses[key] = "conflict"
            elif title and created_id is None:
                statuses[key] = "existing"
            else:
                statuses[key] = "new"
                if write and title:
                    record(
                        session,
                        "receivable_imported",
                        "Título importado do ERP fictício.",
                        title.id,
                        actor_id,
                    )
        for row in rows:
            if statuses.get(row.title_key) == "conflict":
                errors.append(
                    {
                        "line": row.line,
                        "code": "existing_conflict",
                        "message": "Dados divergem do cadastro existente. O lote foi bloqueado.",
                    }
                )
    seen: set[tuple[str, str]] = set()
    rendered: list[dict[str, Any]] = []
    errors_by_line: dict[int, list[str]] = {}
    for error in errors:
        errors_by_line.setdefault(error["line"], []).append(error["message"])
    for row in rows:
        line_errors = errors_by_line.get(row.line, [])
        status = (
            "invalid"
            if line_errors
            else ("duplicate" if row.title_key in seen else statuses.get(row.title_key, "blocked"))
        )
        rendered.append(
            {
                "line": row.line,
                "external_receivable_id": row.external_receivable_id,
                "customer_name": row.customer_name,
                "amount_cents": str(row.amount_cents),
                "due_date": row.due_date.isoformat(),
                "status": status,
                "message": "; ".join(line_errors),
            }
        )
        seen.add(row.title_key)
    return {
        "row_count": len(rows) + len({e["line"] for e in errors if e["code"] == "invalid_row"}),
        "new_count": sum(s == "new" for s in statuses.values()),
        "existing_count": sum(s == "existing" for s in statuses.values()),
        "duplicate_count": len(rows) - len(unique),
        "total_cents": str(sum(row.amount_cents for row in unique.values())),
        "errors": errors,
        "rows": rendered,
    }


def save_lines(session: Session, batch: ImportBatch) -> None:
    session.execute(delete(ImportLine).where(ImportLine.batch_id == batch.id))
    for row in batch.report["rows"]:
        session.add(ImportLine(batch_id=batch.id, line_number=row["line"], data=row))


def create_preview(session: Session, filename: str, content: bytes, actor_id: int) -> ImportBatch:
    if len(content) > MAX_BYTES:
        raise DomainError("file_too_large", "Arquivo maior que 2 MiB.", 413)
    batch = ImportBatch(
        filename=filename.replace("\\", "/").split("/")[-1][:255] or "arquivo.csv",
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        actor_id=actor_id,
        report=analyze(session, content),
    )
    session.add(batch)
    session.flush()
    save_lines(session, batch)
    return batch


class RejectedBatch(Exception):
    def __init__(self, report: dict[str, Any]):
        self.report = report


def confirm_batch(session: Session, batch_id: int, actor_id: int) -> ImportBatch:
    batch = session.scalar(
        select(ImportBatch)
        .where(ImportBatch.id == batch_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if batch is None:
        raise DomainError("not_found", "Lote não encontrado.", 404)
    if batch.status in ("confirmed", "rejected"):
        return batch
    try:
        with session.begin_nested():
            report = analyze(session, batch.content, write=True, actor_id=actor_id)
            if report["errors"]:
                raise RejectedBatch(report)
        batch.status = "confirmed"
    except RejectedBatch as exc:
        report = exc.report
        report["new_count"] = 0
        batch.status = "rejected"
    batch.report = report
    save_lines(session, batch)
    record(
        session,
        "import_" + batch.status,
        "Importação confirmada."
        if batch.status == "confirmed"
        else "Importação rejeitada. A carteira não mudou.",
        actor_id=actor_id,
        details={"batch_id": batch.id},
    )
    return batch
