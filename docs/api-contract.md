# Contrato HTTP v1

Base `/api/v1`, JSON e nomes `snake_case`. Valores `*_cents` são strings de inteiros; datas usam `YYYY-MM-DD` e instantes ISO com fuso. `paid_at` é serializado em UTC. IDs inteiros vão de 1 a 2.147.483.647.

## Sessão e erros

Fontes do contrato local: [`auth.py`](../backend/src/gestao_recebiveis/auth.py), [`schemas.py`](../backend/src/gestao_recebiveis/schemas.py), [`errors.py`](../backend/src/gestao_recebiveis/errors.py). Conferência documental em **22/09/2026**; regras da implementação, não medição de produção.

Cookie `cf_session`; mutações exigem `X-CSRF-Token` e `Origin` do frontend. Erros têm `code`, `message` e `details` opcional. Listas têm `items`, `total`, `page` e `page_size`.

| HTTP | Significado                |
| ---- | -------------------------- |
| 401  | Sessão ausente ou inválida |
| 403  | Permissão ou CSRF          |
| 409  | Conflito                   |
| 422  | Validação                  |

## Rotas

Fontes do contrato local: [`routes.py`](../backend/src/gestao_recebiveis/routes.py), [`responses.py`](../backend/src/gestao_recebiveis/responses.py). Conferência documental em **22/09/2026**; regras da implementação, não medição de produção.

Os caminhos abaixo são relativos a `/api/v1`; saúde e Swagger aparecem separadamente.

| Método e caminho                  | Entrada ou filtros                                        | Retorno                                                                |
| --------------------------------- | --------------------------------------------------------- | ---------------------------------------------------------------------- |
| `POST /auth/login`                | `email`, `password`                                       | `user` com `id`, `email`, `name`, `role`; `csrf_token`                 |
| `GET /auth/session`               | Sessão atual                                              | Mesmo objeto do login                                                  |
| `POST /auth/logout`               | Sessão e CSRF                                             | `ok: true`                                                             |
| `GET /demo`                       | —                                                         | `enabled`, `business_now`, `business_date`, `worker_enabled`, `policy` |
| `POST /demo/clock`                | `business_now`                                            | Estado da demo                                                         |
| `POST /demo/worker`               | `enabled`                                                 | Estado da demo                                                         |
| `POST /demo/scenario`             | `receivable_id`, `scenario`                               | Detalhe do título                                                      |
| `GET /receivables`                | `q`, `status`, `due_from`, `due_to`, `page`, `page_size`  | Lista de títulos                                                       |
| `GET /receivables/{id}`           | ID                                                        | Título, `payment`, `reminders` e `events`                              |
| `POST /receivables/{id}/payments` | `idempotency_key`, `note` opcional                        | Pagamento                                                              |
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

Fontes do contrato local: [`responses.py`](../backend/src/gestao_recebiveis/responses.py). Conferência documental em **22/09/2026**; regras da implementação, não medição de produção.

As listas de campos abaixo resumem os modelos; não são exemplos de JSON executável. Tipos e nulabilidade completos estão em [responses.py](../backend/src/gestao_recebiveis/responses.py).

| Objeto            | Campos                                                                                                                                                                                                            |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Título            | `id`, `source_system`, `external_receivable_id`, `customer_id`, `customer_name`, `customer_email`, `description`, `amount_cents`, `due_date`, `status`, `overdue`, `scenario`                                     |
| Pagamento         | `id`, `amount_cents`, `paid_at`, `recorded_at`; `payment` é `null` quando ausente                                                                                                                                 |
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

Fontes do contrato local: [`request_limits.py`](../backend/src/gestao_recebiveis/request_limits.py), [`database.py`](../backend/src/gestao_recebiveis/database.py), [`routes.py`](../backend/src/gestao_recebiveis/routes.py). Conferência documental em **22/09/2026**; regras da implementação, não medição de produção.

Página 1–10.000, padrão 1; tamanho 1–100, padrão 20; busca `q` até 200 caracteres. Estados de lembrete: `pending`, `processing`, `retry_scheduled`, `sent`, `failed`, `canceled` ou `superseded`. Outros valores retornam 422.

CSV: 2 MiB e 5.000 registros. Multipart: mais 64 KiB de envelope. Outras mutações: até 8 KiB. O limite é aplicado antes do parser, inclusive sem `Content-Length`; excesso retorna 413.

Pool por processo: até 10 conexões, espera por vaga de até 5 s, conexão de 5 s, lock de 5 s e statement de 15 s. Indisponibilidade ou esgotamento do pool retorna 503 com `Retry-After: 2`, sem SQL no corpo. Statement timeout não limita sozinho o tempo total de uma transação com várias instruções.

O e-mail é normalizado; senha é conferida exatamente como recebida, incluindo espaços. Rejeição de importação por regra de negócio retorna HTTP 200 com `status=rejected` e diagnóstico preservado; não representa sucesso financeiro. Erros de HTTP, autenticação ou indisponibilidade usam seus códigos próprios.

## Carteira e recebimentos

Fontes do contrato local: [`receivables.py`](../backend/src/gestao_recebiveis/receivables.py), [`schemas.py`](../backend/src/gestao_recebiveis/schemas.py), [`reporting.py`](../backend/src/gestao_recebiveis/reporting.py). Conferência documental em **22/09/2026**; regras da implementação, não medição de produção.

`overdue` significa título aberto com vencimento estritamente anterior à data comercial. `current` significa título aberto com vencimento igual ou posterior: inclui hoje. Ambos são recortes de consulta; o estado persistido continua `open`. No resumo, `open_cents = overdue_cents + current_cents` e a mesma decomposição vale para as contagens, dentro da busca e do intervalo de vencimento aplicados.

`due_from`/`due_to` afetam apenas a carteira. `received_from`/`received_to` afetam apenas pagamentos pela data comercial da baixa, calculada em São Paulo. A busca `q` é comum aos dois. O intervalo de recebimento padrão vai do primeiro dia do mês comercial à data comercial atual; limites são inclusivos. Espaços externos da busca são removidos; `%`, `_` e barra invertida são tratados literalmente. Intervalos invertidos retornam 422.

Pagamento é sempre **integral**: o valor vem do título bloqueado, não do corpo da requisição. `amount_cents`, `amount_brl` ou qualquer campo adicional são rejeitados com 422 e identificação do campo; nenhuma baixa parcial é gravada. `idempotency_key` aceita 8–100 caracteres e `note` até 500, após remoção de espaços externos. Mesmo título/chave/conteúdo retorna o mesmo pagamento; mesma chave com outro conteúdo retorna 409. `reason` de cancelamento exige 3–500 caracteres após trim.

`enabled` no controle de worker exige booleano JSON real (`true`/`false`), sem aceitar string ou inteiro. `receivable_id` no cenário exige inteiro JSON positivo dentro da faixa dos IDs. Valores fora da faixa são rejeitados antes da consulta ao PostgreSQL.

## Limite do login

Fontes do contrato local: [`login_admission.py`](../backend/src/gestao_recebiveis/login_admission.py). Conferência documental em **22/09/2026**; regras da implementação, não medição de produção.

`POST /api/v1/auth/login` pode retornar `429`, código `login_throttled`, com `Retry-After` em segundos. Cada janela dura 60 segundos desde a primeira reserva: cinco tentativas malsucedidas/em andamento por conta normalizada e origem, e trinta por origem. O limite é consultado antes do Argon2 e persistido mesmo quando a autenticação termina em 401. Uma conta já limitada não consome novamente o orçamento da origem. Credenciais válidas liberam apenas a reserva da própria requisição. Não há um contador global nem bloqueio de conta entre origens distintas.
