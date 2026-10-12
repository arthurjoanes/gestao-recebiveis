# Contrato HTTP v1

Base `/api/v1`, JSON e nomes `snake_case`. Valores `*_cents` são strings de inteiros; datas usam `YYYY-MM-DD` e instantes ISO com fuso. `paid_at` é serializado em UTC. IDs inteiros vão de 1 a 2.147.483.647.

## Sessão e erros

Cookie `cf_session`; mutações exigem `X-CSRF-Token` e `Origin` do frontend. Erros têm `code`, `message` e `details` opcional. Listas têm `items`, `total`, `page` e `page_size`.

| HTTP | Significado                |
| ---- | -------------------------- |
| 401  | Sessão ausente ou inválida |
| 403  | Permissão ou CSRF          |
| 409  | Conflito                   |
| 422  | Validação                  |

## Rotas

Os caminhos abaixo são relativos a `/api/v1`; saúde e Swagger aparecem separadamente.

| Método e caminho                  | Entrada ou filtros                                        | Retorno                                                                |
| --------------------------------- | --------------------------------------------------------- | ---------------------------------------------------------------------- |
| `POST /auth/login`                | `email`, `password`                                       | `user` com `id`, `email`, `name`, `role`; `csrf_token`                 |
| `GET /auth/session`               | Sessão atual                                              | Mesmo objeto do login                                                  |
| `POST /auth/logout`               | Sessão e CSRF                                             | `ok: true`                                                             |
| `GET /demo`                       | Sem entrada                                                         | `enabled`, `business_now`, `business_date`, `worker_enabled`, `policy` |
| `POST /demo/clock`                | `business_now`                                            | Estado da demo                                                         |
| `POST /demo/worker`               | `enabled`                                                 | Estado da demo                                                         |
| `POST /demo/scenario`             | `receivable_id`, `scenario`                               | Detalhe do título                                                      |
| `GET /receivables`                | `q`, `status`, `due_from`, `due_to`, `page`, `page_size`  | Lista de títulos                                                       |
| `GET /receivables/{id}`           | ID                                                        | Título, `payments`, `payment` transitório, `reminders` e `events`                              |
| `POST /receivables/{id}/payments` | `idempotency_key`, `note` e `amount_cents` opcionais                        | Pagamento                                                              |
| `POST /receivables/{id}/cancel`   | `reason`                                                  | Título                                                                 |
| `GET /overview`                   | `q`, `due_from`, `due_to`, `received_from`, `received_to` | Resumo financeiro                                                      |
| `POST /imports`                   | Multipart `file`                                          | Lote completo                                                          |
| `GET /imports`                    | Paginação                                                 | Resumos: `id`, `filename`, `status`, `created_at`, `row_count`         |
| `GET /imports/{id}`               | ID                                                        | Lote completo                                                          |
| `POST /imports/{id}/confirm`      | ID                                                        | Lote `rejected` ou `confirmed`, com relatório                          |
| `GET /reminders`                  | `status`, `q`, `page`, `page_size`                        | Lista de jobs                                                          |
| `GET /reminders/{id}`             | ID                                                        | Job, `attempts` e `delivery`                                           |

Controles da demo exigem operador e modo demo. Cenários: `success`, `transient`, `permanent`, `response_lost` e `always_transient`; só podem mudar antes da primeira tentativa. O relógio demo exige fuso, avanço para frente e anos de 1900 a 2199. Vencimentos aceitam o domínio de datas ISO de Python; a política protege as extremidades contra overflow.

Fora do prefixo: `/health`, `/health/ready` e Swagger `/docs`, com assets locais para demonstração offline. Clientes não possuem editor nesta versão.

## Objetos de resposta

Os campos apresentados resumem os modelos. Consulte os tipos e a nulabilidade completos em [responses.py](../backend/src/gestao_recebiveis/responses.py); as listas servem como referência, sem a sintaxe de objetos JSON executáveis.

| Objeto            | Campos                                                                                                                                                                                                            |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Título            | `id`, `source_system`, `external_receivable_id`, `customer_id`, `customer_name`, `customer_email`, `description`, `amount_cents`, `paid_cents`, `remaining_cents`, `payment_state`, `payments`, `due_date`, `status`, `overdue`, `scenario`                                     |
| Pagamento         | `id`, `amount_cents`, `note`, `paid_at`, `recorded_at`; `payment` é transitório (exatamente um recebimento)                                                                                                                                 |
| Resumo            | `open_cents`, `overdue_cents`, `current_cents`, `received_cents`, `open_count`, `overdue_count`, `current_count`, `paid_count`, `canceled_count`, `business_date`, `received_from`, `received_to`                 |
| Lote completo     | `id`, `filename`, `status`, `created_at`, `report`                                                                                                                                                                |
| Relatório do lote | `row_count`, `new_count`, `existing_count`, `duplicate_count`, `total_cents`, `errors`, `rows`                                                                                                                    |
| Erro do lote      | `line`, `code`, `message`                                                                                                                                                                                         |
| Linha do lote     | `line`, `external_receivable_id`, `customer_name`, `amount_cents`, `due_date`, `status`, `message` opcional                                                                                                       |
| Job               | `id`, `receivable_id`, `external_receivable_id`, `customer_name`, `amount_cents`, `stage`, `status`, `attempts_count`, `next_attempt_at`, `last_error`, `lease_expires_at`, `idempotency_key`, `cancel_requested` |
| Tentativa         | `id`, `number`, `outcome`, `error`, `authorized_at`, `finished_at`                                                                                                                                                |
| Entrega           | `id`, `accepted_at`, `message`, ou `null`                                                                                                                                                                         |
| Evento            | `id`, `type`, `message`, `occurred_at`, `business_at`, `details`                                                                                                                                                  |

A lista de importações não transfere bytes, linhas ou relatório completo. O resumo aplica a busca aos dois recortes; vencimento afeta a carteira, e recebimento afeta pagamentos. Estados de título consultáveis: `open`, `paid`, `canceled`, `overdue` e `current`.

## Limites HTTP

Página 1 a 10.000, padrão 1; tamanho 1 a 100, padrão 20; busca `q` até 200 caracteres. Estados de lembrete: `pending`, `processing`, `retry_scheduled`, `sent`, `failed`, `canceled` ou `superseded`. Outros valores retornam 422.

CSV: 2 MiB e 5.000 registros. Multipart: mais 64 KiB de envelope. Outras mutações: até 8 KiB. O limite é aplicado antes do parser, inclusive sem `Content-Length`; excesso retorna 413.

Pool por processo: até 10 conexões, espera por vaga de até 5 s, conexão de 5 s, lock de 5 s e statement de 15 s. Indisponibilidade ou esgotamento do pool retorna 503 com `Retry-After: 2`, sem SQL no corpo. Statement timeout não limita sozinho o tempo total de uma transação com várias instruções.

O e-mail é normalizado; senha é conferida exatamente como recebida, incluindo espaços. Rejeição de importação por regra de negócio retorna HTTP 200 com `status=rejected` e diagnóstico preservado; não representa sucesso financeiro. Erros de HTTP, autenticação ou indisponibilidade usam seus códigos próprios.

## Carteira e recebimentos

`overdue` significa título aberto com vencimento estritamente anterior à data comercial. `current` significa título aberto com vencimento igual ou posterior: inclui hoje. Ambos são recortes de consulta; o estado persistido continua `open`. No resumo, `open_cents = overdue_cents + current_cents` e a mesma decomposição vale para as contagens, dentro da busca e do intervalo de vencimento aplicados.

`due_from`/`due_to` afetam apenas a carteira. `received_from`/`received_to` afetam apenas pagamentos pela data comercial da baixa, calculada em São Paulo. A busca `q` é comum aos dois. O intervalo de recebimento padrão vai do primeiro dia do mês comercial à data comercial atual; limites são inclusivos. Espaços externos da busca são removidos; `%`, `_` e barra invertida são tratados literalmente. Intervalos invertidos retornam 422.

Pagamento aceita `amount_cents` opcional como string estrita de centavos positivos até `9223372036854775807`. Sem valor, quita o saldo restante. JSON numérico, bool, zero, negativo, expoente, decimal e campos extras são rejeitados com 422. Omitir o valor e informá-lo explicitamente são intenções distintas; alterar essa intenção com a mesma chave retorna 409. `idempotency_key` aceita 8 a 100 caracteres e `note` até 500, após remoção de espaços externos. Mesmo título/chave/conteúdo retorna o mesmo pagamento; mesma chave com outro conteúdo retorna 409. `reason` de cancelamento exige 3 a 500 caracteres após trim.

`enabled` no controle de worker exige booleano JSON real (`true`/`false`), sem aceitar string ou inteiro. `receivable_id` no cenário exige inteiro JSON positivo dentro da faixa dos IDs. Valores fora da faixa são rejeitados antes da consulta ao PostgreSQL.

## Limite do login

`POST /api/v1/auth/login` pode retornar `429`, código `login_throttled`, com `Retry-After` em segundos. Cada janela dura 60 segundos desde a primeira reserva: cinco tentativas malsucedidas/em andamento por conta normalizada e origem, e trinta por origem. O limite é consultado antes do Argon2 e persistido mesmo quando a autenticação termina em 401. Uma conta já limitada não consome novamente o orçamento da origem. Credenciais válidas liberam apenas a reserva da própria requisição. Não há um contador global nem bloqueio de conta entre origens distintas.

## Código e evidências relacionados

| Tema                    | Implementação e critérios                                                                                                                                                       |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Sessão e erros          | [`auth.py`](../backend/src/gestao_recebiveis/auth.py) · [`schemas.py`](../backend/src/gestao_recebiveis/schemas.py) · [`errors.py`](../backend/src/gestao_recebiveis/errors.py) |
| Rotas                   | [`gestao_recebiveis/routes.py`](../backend/src/gestao_recebiveis/routes.py)                                                                                                     |
| Limites HTTP            | [`request_limits.py`](../backend/src/gestao_recebiveis/request_limits.py) · [`database.py`](../backend/src/gestao_recebiveis/database.py)                                       |
| Carteira e recebimentos | [`receivables.py`](../backend/src/gestao_recebiveis/receivables.py) · [`reporting.py`](../backend/src/gestao_recebiveis/reporting.py)                                           |
| Limite do login         | [`login_admission.py`](../backend/src/gestao_recebiveis/login_admission.py)                                                                                                     |

## Parcelas e relatórios — 12/10/2026

Título em lista/detalhe inclui `paid_cents`, `remaining_cents`, `payment_state` (`unpaid`, `partial`, `paid`). Listas e detalhe expõem `payments[]` por `paid_at`, depois `id`. O campo singular `payment` está depreciado: existe somente com exatamente um recebimento e retorna `null` com zero ou vários. Cada resposta de pagamento preserva valor, nota e instantes imutáveis, sem saldo corrente.

Cancelamento de título com qualquer recebimento retorna 409. Cancelamento já confirmado conserva sua idempotência. Uma parcela não cancela nem acrescenta etapas de lembrete. Cada tentativa mostra `authorized_remaining_cents` e `authorized_at`; o valor é o snapshot da autorização, inclusive quando o saldo atual já mudou.

| GET autenticado | Filtros | Retorno |
| --- | --- | --- |
| `/reports/aging` | `q`, `customer_id`, `due_from`, `due_to`, `bucket`, `page`, `page_size` | Metadados, `open_cents`, `title_count`, `buckets[]`, `items`, `total`, `page`, `page_size` |
| `/customers/{id}/statement` | `q`, `status`, vencimento, recebimento, `page`, `page_size`, `payment_page`, `payment_page_size` | `customer`, `totals`, páginas `titles` e `payments`, metadados e filtros |

As chaves de faixa são `current`, `1_30`, `31_60`, `61_90`, `over_90`. A lista `/receivables` aceita `customer_id` e `aging_bucket` para preservar o drill-down. Reader pode consultar os dois relatórios. IDs, datas, busca e paginação conservam os limites HTTP; filtros inválidos retornam 422. Não existe `as_of` histórico. Fronteiras, totais e independência dos períodos estão no [contrato detalhado](evolucao-20261012.md).

### Conferência e recuperação na interface

Novas quitações pela interface congelam `amount_cents` com o valor mostrado na confirmação. Se outro recebimento reduzir o saldo antes do commit, o servidor rejeita o valor maior que o residual; a interface atualiza a posição e permite revisar a intenção. Pedidos locais v1 antigos com valor omitido conservam corpo e chave originais. A prévia local não participa do payload HTTP nem do hash idempotente.

Timeout de 30 segundos, resposta inválida ou perda de conexão conservam a intenção para recuperação. Logout retira conteúdo protegido imediatamente e limpa intenções locais; respostas de uma sessão anterior são descartadas. Um 403 revalida a sessão e suas permissões. Esses comportamentos e limites estão na [revisão da interface](uiux-20261012.md).
