"""Validação do arquivo exportado: não consulta nem altera a carteira."""

import csv
import io
import re
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from email_validator import EmailNotValidError, validate_email

COLUMNS = [
    "source_system",
    "external_receivable_id",
    "external_customer_id",
    "customer_name",
    "customer_email",
    "description",
    "amount_brl",
    "due_date",
]
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000
MONEY = re.compile(r"^[0-9]+(?:\.[0-9]{1,2})?$")


@dataclass(frozen=True)
class Row:
    line: int
    source_system: str
    external_receivable_id: str
    external_customer_id: str
    customer_name: str
    customer_email: str
    description: str
    amount_cents: int
    due_date: date

    @property
    def customer_key(self) -> tuple[str, str]:
        return self.source_system, self.external_customer_id

    @property
    def title_key(self) -> tuple[str, str]:
        return self.source_system, self.external_receivable_id

    def comparable(self) -> dict[str, Any]:
        fields = asdict(self)
        fields.pop("line")
        return fields


def cents(value: str) -> int:
    if not MONEY.fullmatch(value):
        raise ValueError("Use ponto decimal e até duas casas, sem sinal ou expoente.")
    result = int(Decimal(value) * 100)
    if not 0 < result <= 9223372036854775807:
        raise ValueError("Valor deve ser positivo e caber em centavos inteiros de 64 bits.")
    return result


def parse(content: bytes) -> tuple[list[Row], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    rows: list[Row] = []
    if not content or len(content) > MAX_BYTES:
        return [], [
            {"line": 0, "code": "file_size", "message": "Arquivo vazio ou maior que 2 MiB."}
        ]
    try:
        text = content.decode("utf-8-sig")
        if "\x00" in text:
            raise ValueError("O arquivo contém caractere NUL.")
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        columns = next(reader, None)
        if not columns or len(columns) != len(COLUMNS) or set(columns) != set(COLUMNS):
            raise ValueError("Cabeçalho inválido. Use exatamente as oito colunas do contrato.")
        count = 0
        while True:
            line = reader.line_num + 1
            try:
                values = next(reader)
            except StopIteration:
                break
            if not values:
                continue
            count += 1
            if count > MAX_ROWS:
                raise ValueError("Limite de 5.000 linhas excedido.")
            try:
                if len(values) != len(COLUMNS):
                    raise ValueError("Quantidade de campos diferente do cabeçalho.")
                data = {
                    column: value.strip() for column, value in zip(columns, values, strict=True)
                }
                limits = {
                    "source_system": 80,
                    "external_receivable_id": 100,
                    "external_customer_id": 100,
                    "customer_name": 200,
                    "customer_email": 254,
                    "description": 500,
                }
                for column, limit in limits.items():
                    if not data[column] or len(data[column]) > limit:
                        raise ValueError(f"{column}: obrigatório, até {limit} caracteres.")
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["due_date"]):
                    raise ValueError("Vencimento deve usar YYYY-MM-DD.")
                try:
                    due = date.fromisoformat(data["due_date"])
                except ValueError as exc:
                    raise ValueError("Data de vencimento inválida.") from exc
                try:
                    email = validate_email(
                        data["customer_email"], check_deliverability=False
                    ).normalized
                except EmailNotValidError as exc:
                    raise ValueError(
                        "E-mail do cliente inválido; exemplo: cliente@example.com."
                    ) from exc
                rows.append(
                    Row(
                        line,
                        data["source_system"],
                        data["external_receivable_id"],
                        data["external_customer_id"],
                        data["customer_name"],
                        email,
                        data["description"],
                        cents(data["amount_brl"]),
                        due,
                    )
                )
            except (ValueError, EmailNotValidError) as exc:
                errors.append({"line": line, "code": "invalid_row", "message": str(exc)})
        if count == 0:
            raise ValueError("Arquivo não contém títulos.")
    except UnicodeError:
        errors.append(
            {
                "line": 0,
                "code": "invalid_file",
                "message": "Use um arquivo UTF-8.",
            }
        )
    except csv.Error:
        errors.append(
            {
                "line": 0,
                "code": "invalid_file",
                "message": "CSV malformado. Confira aspas e campos.",
            }
        )
    except ValueError as exc:
        errors.append({"line": 0, "code": "invalid_file", "message": str(exc)})
    title_groups: dict[tuple[str, str], list[Row]] = {}
    customer_groups: dict[tuple[str, str], list[Row]] = {}
    for row in rows:
        title_groups.setdefault(row.title_key, []).append(row)
        customer_groups.setdefault(row.customer_key, []).append(row)
    for group in title_groups.values():
        if any(row.comparable() != group[0].comparable() for row in group):
            for row in group:
                errors.append(
                    {
                        "line": row.line,
                        "code": "contradictory_title",
                        "message": "Título contraditório no próprio arquivo.",
                    }
                )
    for group in customer_groups.values():
        if any(
            (row.customer_name, row.customer_email)
            != (group[0].customer_name, group[0].customer_email)
            for row in group
        ):
            for row in group:
                errors.append(
                    {
                        "line": row.line,
                        "code": "contradictory_customer",
                        "message": "Dados do cliente divergem no arquivo.",
                    }
                )
    return rows, errors
