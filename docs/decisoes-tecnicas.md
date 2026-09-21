# Decisões técnicas

Perguntas que este projeto levanta, com a resposta curta e o arquivo onde ela está no código. As respostas apontam para `backend/src/gestao_recebiveis/` salvo indicação diferente.

## Por que a fila de jobs fica no PostgreSQL e não em um broker?

Os lembretes já dividem título, pagamento e cancelamento no mesmo banco. Deixar a fila lá reaproveita os mesmos locks e as mesmas transações, sem subir outro serviço para o portfólio rodar. O `claim` busca job elegível com `with_for_update(skip_locked=True)`, que é o SELECT ... FOR UPDATE SKIP LOCKED do PostgreSQL. Fica em `reminders/service.py` (função `claim`) e no modelo `Reminder` em `models.py`.

## Onde as transações começam e terminam?

Na API, `get_session` abre a transação com `SessionLocal.begin()` e o commit acontece ao sair do `with`, antes da resposta ir ao cliente. Os casos de uso não fazem commit por conta própria; quem abre o escopo é a dependência. O worker e o seed abrem as próprias transações e chamam os mesmos casos de uso. Ver `database.py` (`get_session`) e `worker.py` (`run_once`, que abre um `begin()` por passo: schedule, claim, authorize, finish).

## Como distingo intenção, tentativa e entrega de um lembrete?

São três tabelas. `Reminder` é a intenção de uma etapa (D-3, D0, D+3, D+7) para um título; `Attempt` é uma tentativa autorizada dessa intenção; `Delivery` é a entrega simulada aceita pelo provedor. As tentativas da mesma intenção reusam a `idempotency_key` do `Reminder`, então repetir não vira outra intenção. Modelos em `models.py`; o fluxo está em `reminders/service.py` e `reminders/provider.py`.

## Por que dinheiro em centavos inteiros e não float?

Guardo o valor em `amount_cents` como BigInteger, com check `amount_cents > 0` no banco. A entrada vem como string decimal, é convertida com `Decimal` e recusada se tiver mais de duas casas ou sinal. Somas, totais e ordenações usam inteiro, então não aparece erro de arredondamento de ponto flutuante. Ver `import_csv.py` (função `cents`, com o `int(Decimal(value) * 100)`) e `models.py` (`Receivable.amount_cents`).

## Como a importação repetida ou reordenada não duplica títulos?

A chave de negócio é `(source_system, external_receivable_id)`, com unique constraint no banco. O `analyze` insere com `ON CONFLICT DO NOTHING`, relê o registro bloqueado e compara campo a campo; igual vira `existing`, divergente vira `conflict` e bloqueia o lote inteiro sem escrever título novo. Reordenar linhas ou renomear o arquivo não muda a chave, então não duplica. Ver `imports.py` (`analyze`) e a unique constraint em `models.py`.

## Como a baixa é idempotente?

Antes de gravar, `pay` pega um `pg_advisory_xact_lock` derivado da `idempotency_key`, o que serializa a mesma chave mesmo em títulos diferentes. Se já existe pagamento com aquela chave, comparo o `request_hash`: conteúdo igual devolve o mesmo pagamento, conteúdo diferente levanta conflito (409). Repetir a chamada não cria outra baixa. Ver `receivables.py` (função `pay`) e `models.py` (`Payment.idempotency_key`, `request_hash`).

## Por que o pagamento é sempre integral?

O valor vem do título bloqueado (`title.amount_cents`), não do corpo da requisição. A rota rejeita `amount_cents`, `amount_brl` ou qualquer campo extra com 422, então não há como registrar baixa parcial. Isso mantém o escopo de portfólio em pagamento integral. Ver `receivables.py` (`pay`) e `docs/api-contract.md` (seção de pagamento).

## Como o pagamento mexe em lembretes já planejados?

O `pay` chama `cancel_pending` na mesma transação, depois de bloquear o título. Os jobs ativos passam a `canceled` ou, se havia tentativa com resposta desconhecida, ficam marcados para reconciliar antes de encerrar. Uma baixa confirmada impede novas autorizações; uma autorização anterior pode já estar em trânsito e continua rastreável, sem promessa de desfazer. Ver `receivables.py` (`pay`) e `reminders/service.py` (`cancel_pending` e a checagem `title.status != "open"` em `authorize`).

## O que acontece em cada ponto de falha (retry, lease, reconciliação, restart)?

O provedor persiste `ProviderResult` e `Delivery` no mesmo banco antes de a resposta se perder, então o resultado sobrevive a restart. Resposta desconhecida vira `retry_scheduled` e, na próxima passada, `authorize` reconcilia a mesma tentativa em vez de mandar de novo. Se o processo morre, o job fica `processing` com lease vencido e o `claim` o recupera. Ver `reminders/provider.py` (`FakeProvider.send`, `ResponseLost`), `reminders/service.py` (`claim`, `authorize`, `finish`) e o roteiro em `tests/persistence_probe.py`.

## Como dois workers não produzem dois efeitos para o mesmo job?

O `claim` usa SKIP LOCKED e incrementa `lease_token`, que é o token de posse. `authorize`, `renew` e `finish` só agem se `_owned` confirmar que o token e o lease ainda batem; uma resposta atrasada de um worker antigo é recusada porque o token subiu. O lease padrão é 60s com renovação a cada 20s (`config.py`). Ver `reminders/service.py` (`claim`, `_owned`, `renew`, `finish`).

## Quais são os limites da simulação do provedor?

O `FakeProvider` grava resultado por tentativa e entrega única por chave no PostgreSQL, o que deixa testar sucesso, falha transitória, falha permanente e resposta perdida com estado durável. Isso mostra a recuperação local após restart, mas não diz nada sobre entrega por um serviço externo nem sobre exactly-once fora daqui. Nenhuma mensagem sai para destinatário real; tudo fica no banco e na interface. Ver `reminders/provider.py`.

## Como evoluir para um provedor real sem fingir que já existe?

O worker fala com a interface `MessageProvider` (um `Protocol`), então um provedor real seria outra classe com o método `send`, sem mexer em `authorize`/`finish`. Antes de plugar, eu checaria o contrato de idempotência e de reconciliação do serviço, porque a resposta perdida e a repetição de chave dependem desse comportamento. Hoje só existe o `FakeProvider`; a troca é um caminho, não algo implementado. Ver `reminders/provider.py` (`MessageProvider`, `FakeProvider`) e `worker.py` (`run_once`, parâmetro `provider`).
