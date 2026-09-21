import argparse
import csv
import hashlib
import io
import json
import random
from datetime import date, timedelta
from pathlib import Path

GENERATOR_VERSION = 1
DEFAULT_REFERENCE = date(2026, 8, 17)
CSV_COLUMNS = [
    "source_system",
    "external_receivable_id",
    "external_customer_id",
    "customer_name",
    "customer_email",
    "description",
    "amount_brl",
    "due_date",
]


def encode_csv(rows: list[dict[str, str]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def generate_rows(
    seed: int = 42,
    reference: date = DEFAULT_REFERENCE,
    customers: int = 60,
    receivables: int = 240,
) -> list[dict[str, str]]:
    if customers < 1 or receivables < customers or receivables > 5000:
        raise ValueError(
            "Use 1 a 5.000 clientes e até 5.000 títulos, com pelo menos um por cliente."
        )
    rng = random.Random(seed)
    names = ["Aurora", "Jardim", "Horizonte", "Brisa", "Cedro", "Luar", "Nuvem", "Ipê"]
    rows = []
    offsets = [-30, -15, -8, -7, -3, -1, 0, 1, 3, 7, 15, 30]
    for index in range(1, receivables + 1):
        customer = (index - 1) % customers + 1
        cents = rng.randint(5000, 550000)
        due = reference + timedelta(days=offsets[(index - 1) % len(offsets)])
        rows.append(
            {
                "source_system": "erp_ficticio_v1",
                "external_receivable_id": f"TIT-{index:04d}",
                "external_customer_id": f"CLI-{customer:03d}",
                "customer_name": f"Empório {names[(customer - 1) % len(names)]} {customer:03d} (fictício)",
                "customer_email": f"cliente{customer:03d}@example.com",
                "description": f"Mercadorias fictícias • pedido {index:04d}",
                "amount_brl": f"{cents // 100}.{cents % 100:02d}",
                "due_date": due.isoformat(),
            }
        )
    return rows


def write_data(output: Path, seed: int, reference: date, customers: int, receivables: int) -> None:
    output.mkdir(parents=True, exist_ok=True)
    content = encode_csv(generate_rows(seed, reference, customers, receivables))
    (output / "portfolio.csv").write_bytes(content)
    manifest = {
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "reference_date": reference.isoformat(),
        "business_timezone": "America/Sao_Paulo",
        "customers": customers,
        "receivables": receivables,
        "sha256": hashlib.sha256(content).hexdigest(),
        "source": "Clientes e títulos fictícios.",
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera CSV de títulos fictícios.")
    parser.add_argument("--output", type=Path, default=Path("/data/generated"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reference", type=date.fromisoformat, default=DEFAULT_REFERENCE)
    parser.add_argument("--customers", type=int, default=60)
    parser.add_argument("--receivables", type=int, default=240)
    args = parser.parse_args()
    write_data(args.output, args.seed, args.reference, args.customers, args.receivables)
    print(f"CSV e manifesto gravados em {args.output}")


if __name__ == "__main__":
    main()
