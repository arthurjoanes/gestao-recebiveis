# Contrato HTTP v1
Base /api/v1; JSON; valores *_cents são strings de inteiros. Datas YYYY-MM-DD e instantes ISO com fuso; `paid_at` de pagamentos é serializado em UTC. IDs inteiros de 1 a 2.147.483.647. Erros {code,message,details?}; 401 sessão, 403 permissão/CSRF, 409 conflito, 422 validação.
Listas {items,total,page,page_size}. Filtros de títulos: q,status(open/paid/canceled/overdue/current),due_from,due_to,page(default1),page_size(default20 max100).
POST /auth/login {email,password} -> {user:{id,email,name,role},csrf_token}; GET /auth/session mesmo retorno; POST /auth/logout -> {ok:true}. Cookie cf_session; mutações com X-CSRF-Token e Origin do frontend.
GET /demo -> {enabled,business_now,business_date,worker_enabled,policy}; POST /demo/clock {business_now}; POST /demo/worker {enabled}; POST /demo/scenario {receivable_id,scenario} (success,transient,permanent,response_lost,always_transient). Controles somente demo operador; mudança de cenário antes da primeira tentativa.
GET /receivables filtros -> itens {id,source_system,external_receivable_id,customer_id,customer_name,customer_email,description,amount_cents,due_date,status,overdue,scenario}.
GET /receivables/{id} -> mesmo item + payment (null ou {id,amount_cents,paid_at,recorded_at}), reminders e events.
POST /receivables/{id}/payments {idempotency_key,note?} -> payment; POST /receivables/{id}/cancel {reason} -> título.
GET /overview?q=&due_from=&due_to=&received_from=&received_to= -> {open_cents,overdue_cents,current_cents,received_cents,open_count,overdue_count,current_count,paid_count,canceled_count,business_date,received_from,received_to}. Recebido aplica q e datas recebimento, carteira aplica q e vencimento; definições visíveis.
POST /imports multipart file -> batch; GET /imports lista de resumos {id,filename,status,created_at,row_count}, sem bytes/linhas/relatório; GET /imports/{id} -> batch completo; POST /imports/{id}/confirm -> batch (status rejected ou confirmed, relatório no corpo).
Batch {id,filename,status,created_at,report:{row_count,new_count,existing_count,duplicate_count,total_cents,errors:[{line,code,message}],rows:[{line,external_receivable_id,customer_name,amount_cents,due_date,status,message?}]}}.
GET /reminders?status=&q=&page=&page_size= -> lista de jobs; GET /reminders/{id} -> job + attempts/delivery.
Job {id,receivable_id,external_receivable_id,customer_name,amount_cents,stage,status,attempts_count,next_attempt_at,last_error,lease_expires_at,idempotency_key,cancel_requested}; attempt {id,number,outcome,error,authorized_at,finished_at}; delivery {id,accepted_at,message} ou null.
Events {id,type,message,occurred_at,business_at,details}. Clientes não possuem editor nesta versão.
Health /health e /health/ready. Swagger /docs auto-hospedado para demonstração offline.
Relógio demo aceita anos 1900–2199, timezone obrigatório e avanço para frente. Datas civis de vencimento aceitam o domínio ISO de Python, com política protegida contra overflow nas extremidades.

## Limites HTTP

Página 1–10.000; tamanho 1–100, padrão 20; busca `q` até 200 caracteres. Estados de lembrete: `pending`, `processing`, `retry_scheduled`, `sent`, `failed`, `canceled` ou `superseded`. Outros valores retornam 422.

CSV: 2 MiB e 5.000 registros. Multipart: mais 64 KiB de envelope. Outras mutações: até 8 KiB. O limite é aplicado antes do parser, inclusive sem `Content-Length`; excesso retorna 413.

Pool por processo: até 10 conexões, espera por vaga de até 5 s, conexão de 5 s, lock de 5 s e statement de 15 s. Indisponibilidade ou esgotamento do pool retorna 503 com `Retry-After: 2`, sem SQL no corpo. Statement timeout não limita sozinho o tempo total de uma transação com várias instruções.

O e-mail é normalizado; senha é conferida exatamente como recebida, incluindo espaços. Rejeição de importação por regra de negócio retorna HTTP 200 com `status=rejected` e diagnóstico preservado; não representa sucesso financeiro. Erros de HTTP, autenticação ou indisponibilidade usam seus códigos próprios.


## Carteira e recebimentos

`overdue` significa título aberto com vencimento estritamente anterior à data comercial. `current` significa título aberto com vencimento igual ou posterior: inclui hoje. Ambos são recortes de consulta; o estado persistido continua `open`. No resumo, `open_cents = overdue_cents + current_cents` e a mesma decomposição vale para as contagens, dentro da busca e do intervalo de vencimento aplicados.

`due_from`/`due_to` afetam apenas a carteira. `received_from`/`received_to` afetam apenas pagamentos pela data comercial da baixa, calculada em São Paulo. A busca `q` é comum aos dois. O intervalo de recebimento padrão vai do primeiro dia do mês comercial à data comercial atual; limites são inclusivos. Espaços externos da busca são removidos; `%`, `_` e barra invertida são tratados literalmente. Intervalos invertidos retornam 422.

Pagamento é sempre **integral**: o valor vem do título bloqueado, não do corpo da requisição. `amount_cents`, `amount_brl` ou qualquer campo adicional são rejeitados com 422 e identificação do campo; nenhuma baixa parcial é gravada. `idempotency_key` aceita 8–100 caracteres e `note` até 500, após remoção de espaços externos. Mesmo título/chave/conteúdo retorna o mesmo pagamento; mesma chave com outro conteúdo retorna 409. `reason` de cancelamento exige 3–500 caracteres após trim.

`enabled` no controle de worker exige booleano JSON real (`true`/`false`), sem aceitar string ou inteiro. `receivable_id` no cenário exige inteiro JSON positivo dentro da faixa dos IDs. Valores fora da faixa são rejeitados antes da consulta ao PostgreSQL.
