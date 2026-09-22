# Dados de demonstração

## Origem e formato

Gerador próprio, clientes inventados identificados como fictícios e e-mails `example.com`. Sem CPF, telefone, boleto ou dados de clientes reais. O CSV usa UTF-8 (BOM aceito), vírgula e aspas CSV padrão; o limite é **2 MiB e 5.000 registros**.

```csv
source_system,external_receivable_id,external_customer_id,customer_name,customer_email,description,amount_brl,due_date
```

## Campos e limites

Todos os campos são obrigatórios. Espaços externos são removidos; IDs são sensíveis a maiúsculas. Campos desconhecidos e cabeçalhos duplicados são rejeitados.

| Campo                    | Limite ou regra após trim                                                                 |
| ------------------------ | ----------------------------------------------------------------------------------------- |
| `source_system`          | Até 80 caracteres                                                                         |
| `external_receivable_id` | Até 100 caracteres                                                                        |
| `external_customer_id`   | Até 100 caracteres                                                                        |
| `customer_name`          | Até 200 caracteres                                                                        |
| `customer_email`         | Até 254 caracteres e sintaxe válida                                                       |
| `description`            | Até 500 caracteres                                                                        |
| `amount_brl`             | Decimal positivo com ponto, até duas casas; sem sinal, expoente ou milhar, como `1250.09` |
| `due_date`               | Data civil ISO de `0001-01-01` a `9999-12-31`, com calendário válido                      |

O máximo financeiro é **9.223.372.036.854.775.807 centavos**. Fonte dos campos, faixas e parsing: [import_csv.py](../backend/src/gestao_recebiveis/import_csv.py); critérios em [test_field_matrix.py](../backend/tests/test_field_matrix.py).

## Repetição e diagnóstico

A comparação considera nome/e-mail do cliente e todos os campos importados do título. Duplicata idêntica não altera estado financeiro. Conflitos bloqueiam o lote inteiro; linhas de diagnóstico permanecem. Fontes: [importação](../backend/src/gestao_recebiveis/imports.py) e [testes financeiros](../backend/tests/test_financial.py).

Campos entre aspas podem conter vírgulas, aspas escapadas e quebras de linha. Linhas fisicamente vazias entre registros são ignoradas e não consomem o limite de registros. `line` identifica a linha física em que o registro começa, inclusive depois de campos multilinha; `line=0` indica erro do arquivo inteiro.

A prévia da interface exibe **50 registros por página** e conserva todos os diagnósticos, também paginados quando necessário. Fontes: [parser](../backend/src/gestao_recebiveis/import_csv.py) e [prévia](../frontend/src/features/import-preview.tsx).

## Massa padrão e fixture

O gerador usa seed `42`, versão `1`, referência `2026-08-17`, **60 clientes e 240 títulos**. O manifesto acompanha o CSV. A fixture manual é separada e contém centavos verificáveis sem reutilizar o algoritmo. Fontes: [gerador](../backend/src/gestao_recebiveis/generator.py), [seed](../backend/src/gestao_recebiveis/seed.py) e [amostras](../data/samples).
