# Exportações fictícias

`generated/portfolio.csv`: 60 clientes, 240 títulos, seed 42, referência 2026-08-17. O manifesto contém a configuração e o SHA-256.

`samples/valid.csv` contém três títulos, dois clientes e soma **R$ 2.000,00**. Importe antes de usar `conflicting.csv`; este contém uma mudança proibida no DEMO-001 e um título novo que não pode entrar parcialmente. `repeated.csv` é cópia exata de `valid.csv`; `reordered.csv` muda apenas a ordem. `invalid.csv` contém valor com três casas e data impossível; `empty.csv` tem zero bytes; `contradictory.csv` repete a mesma chave com valores diferentes.

`fixtures/manual.csv` é escrito manualmente, independente do gerador: 10 + 20 + 123456 = **123486 centavos (R$ 1.234,86)**. Às 10:00 de 17/08/2026, somente MANUAL-01 está vencido; MANUAL-02 vence no dia e MANUAL-03 vence no futuro. A baixa de MANUAL-02 deixa **123466 centavos abertos**, **10 vencidos** e **20 recebidos**.

CSV: UTF-8, vírgula, cabeçalho fixo, datas ISO, `amount_brl` com ponto decimal e até duas casas. Veja [contrato de dados](../docs/data-contract.md).
