# Decisões técnicas

Organizei a implementação para proteger três resultados: uma dívida não se repete ao importar, uma baixa não se repete ao pagar e uma tentativa incerta de envio não é tratada como uma entrega nova. O [guia de problemas e exemplos](problem-solution.md) mostra os casos, o resultado esperado e os testes correspondentes. As respostas abaixo detalham o mecanismo; caminhos sem link completo se referem a `backend/src/gestao_recebiveis/`.

## Dificuldades verificáveis e suas consequências

| Dificuldade | Tratamento escolhido | Consequência que permanece |
| --- | --- | --- |
| A carteira pode mudar entre prévia e confirmação do CSV | Revalidar sob transação e rejeitar o lote conflitante por inteiro | O operador precisa corrigir e reenviar também suas linhas válidas |
| Pagamento e autorização de lembrete podem disputar o mesmo título | Ordem de locks e baixa/cancelamento na mesma transação | Uma autorização já feita pode produzir efeito depois da baixa |
| A aceitação sobrevive, mas sua resposta se perde | Guardar tentativa desconhecida e reconciliar sua mesma identidade | A integração real depende do que o provedor permite consultar e repetir |
| Verificar senhas consome CPU antes de saber se o usuário é legítimo | Reservar capacidade persistente antes do Argon2 | Na demo, clientes que atravessam o mesmo Next compartilham a origem e a quota |
| O runtime não precisa administrar o banco | Separar admin, owner e aplicação; reaplicar concessões na atualização | A instalação exige provisionamento e preservação das credenciais corretas |

As três primeiras situações têm regressões financeiras/de lembretes referenciadas no [guia de problemas](problem-solution.md). As duas últimas foram tratadas na [revisão de segurança](security.md). São dificuldades demonstradas pelo código e pelos testes; não são relatos de incidentes com clientes ou de experiência pessoal não registrada.

## Por que a fila de jobs fica no PostgreSQL e não em um broker?

Mantive os lembretes no banco que já contém título, pagamento e cancelamento. A fila reaproveita os mesmos locks e as mesmas transações, sem subir outro serviço para o portfólio rodar. O `claim` busca job elegível com `with_for_update(skip_locked=True)`, que é o SELECT ... FOR UPDATE SKIP LOCKED do PostgreSQL. Fica em `reminders/service.py` (função `claim`) e no modelo `Reminder` em `models.py`.

## Onde as transações começam e terminam?

Na API, `get_session` abre a transação com `SessionLocal.begin()` e o commit acontece ao sair do `with`, antes da resposta ir ao cliente. Os casos de uso não fazem commit por conta própria; quem abre o escopo é a dependência. O worker e o seed abrem as próprias transações e chamam os mesmos casos de uso. Ver `database.py` (`get_session`) e `worker.py` (`run_once`, que abre um `begin()` por passo: schedule, claim, authorize, finish).

## Como distingo intenção, tentativa e entrega de um lembrete?

Separei três tabelas. `Reminder` é a intenção de uma etapa (D-3, D0, D+3, D+7) para um título; `Attempt` é uma tentativa autorizada dessa intenção; `Delivery` é a entrega simulada aceita pelo provedor. As tentativas da mesma intenção reusam a `idempotency_key` do `Reminder`, então repetir não vira outra intenção. Modelos em `models.py`; o fluxo está em `reminders/service.py` e `reminders/provider.py`.

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

O worker fala com a interface `MessageProvider` (um `Protocol`), mas implementar `send` não basta para comprovar uma integração real. É necessário verificar idempotência, consulta de resultado e recuperação após resposta perdida, inclusive depois de restaurar um banco antigo. O [plano do adaptador](provider-integration-plan.md) registra as decisões e os ensaios que dependem de um fornecedor escolhido; o contrato poderá exigir mudanças adicionais. Hoje só existe o `FakeProvider`. Ver `reminders/provider.py` (`MessageProvider`, `FakeProvider`) e `worker.py` (`run_once`, parâmetro `provider`).

## Por que a interface usa carteira, conferência e detalhe de tentativas?

São três tarefas diferentes. A carteira precisa comparar cliente, vencimento, valor e situação lado a lado; por isso a tabela recebe o espaço principal e os filtros ficam próximos. A importação exige uma decisão antes de escrever: arquivo, conferência e confirmação são passos visíveis, mas a validação definitiva permanece no servidor. Nos lembretes, abrir a cronologia não deve apagar o recorte da fila; o detalhe aparece junto da lista no desktop e acima dela no celular.

Voltar de um título conserva os filtros e a página, e recupera o foco quando a linha ainda existe. Se um pagamento ou outra alteração removeu o título daquele recorte, o retorno tem um destino acessível e a página vazia explica como continuar. A mesma regra orienta os estados vazio, carregando e erro: indicar o que aconteceu e oferecer a próxima ação, sem trocar uma falha de consulta por um saldo zero.

O custo dessa composição é manter explicitamente o contexto entre lista e detalhe. Isso fica em [`workspace.tsx`](../frontend/src/features/workspace.tsx) e [`receivables.tsx`](../frontend/src/features/receivables.tsx), com regressões no [roteiro de navegador](../frontend/tests/journey.spec.ts). No celular, as linhas da carteira e dos vencidos reorganizam valor, cliente e situação; a ação fica no código do título, sem repetir um segundo botão na mesma linha. A rolagem horizontal, quando necessária em outras tabelas, fica dentro da região; o menu móvel e os diálogos mantêm teclado, Escape e retorno de foco.

No candidato atual, agrupei o saldo aberto com suas parcelas vencido/em dia e separei recebido em outra superfície, com datas próprias. Os quatro valores ficam visíveis sem abrir disclosure; isso mantém posição da carteira e entradas no período distintas. A [matriz do frontend](frontend-quality.md) registra que essa composição ainda não foi executada no navegador. A área de trabalho tem largura máxima e margens centrais em monitores largos; valores usam alinhamento numérico e o texto mantém seu eixo de leitura. Regras dessa composição ficam em [`financial-workspace.css`](../frontend/src/app/financial-workspace.css), enquanto controles compartilhados permanecem em `globals.css`. Foram removidas as regras da antiga barra lateral, evitando dois layouts concorrentes. Transições curtas de cor sinalizam interação; a preferência por movimento reduzido as desativa.

## Por que limitar o login antes de conferir a senha e separar as contas do banco?

Verificar uma senha com Argon2 tem custo deliberado. Fazer isso antes de reservar capacidade permitiria gastar esse custo repetidamente sem uma cota atômica. [`login_admission.py`](../backend/src/gestao_recebiveis/login_admission.py) reserva a tentativa em transação independente: falhar a autenticação não desfaz a reserva, e um sucesso libera somente a própria. Identificadores dos contadores usam HMAC; o relógio comercial da demo não muda a expiração. A [suíte de admissão](../backend/tests/test_login_admission.py) verifica concorrência e as reservas.

As contas de administração e migração precisam alterar a estrutura; API e worker precisam apenas manipular dados. [`provision_database.py`](../backend/src/gestao_recebiveis/provision_database.py) separa essas permissões, conferidas em [test_database_roles.py](../backend/tests/test_database_roles.py). O custo é provisionar identidades adicionais e migrar instalações antigas com cuidado. Isso limita o privilégio do runtime, mas não substitui a autorização por papel nem resolve sozinho a identificação de clientes atrás de proxies; esses limites e o procedimento estão em [segurança](security.md).
