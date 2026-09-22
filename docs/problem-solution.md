# Do problema financeiro ao comportamento verificável

> Regras e critérios de teste. Fontes: [financeiro](../backend/tests/test_financial.py), [lembretes](../backend/tests/test_reminders.py) e [API](../backend/tests/test_api.py). Conferência documental: **22/09/2026**.

Desenvolvi o projeto para exercitar uma operação de contas a receber: conferir títulos vindos de outro sistema, registrar o pagamento integral e acompanhar lembretes. A demonstração representa uma empresa fictícia, em BRL. Não emite boleto, não cobra por Pix e não envia mensagens a clientes reais.

## Um arquivo reenviado não deve criar outra dívida

Um nome de arquivo ou seu hash identificam bytes, mas não identificam uma dívida. Renomear o CSV ou trocar a ordem das linhas muda essa apresentação sem criar uma nova obrigação financeira.

Usei o par `source_system` e `external_receivable_id` como identidade do título, protegido por unicidade no banco. Na confirmação, `analyze` insere quando possível, bloqueia e compara o registro existente. Dados iguais tornam a linha existente; divergência bloqueia o lote. A prévia não reserva a carteira: outro operador pode alterá-la antes da confirmação, por isso o servidor revalida tudo nesse momento.

**Exemplo:** [valid.csv](../data/samples/valid.csv) contém R$ 1.250,09, R$ 480,10 e R$ 269,81, totalizando R$ 2.000,00 em três títulos. Reimportar [reordered.csv](../data/samples/reordered.csv) mantém os mesmos três títulos. Já [conflicting.csv](../data/samples/conflicting.csv) tenta mudar `DEMO-001` e incluir `DEMO-004`: a rejeição não deixa esse novo título pela metade na carteira.

**Por que assim:** a chave de negócio protege o efeito mesmo com concorrência. O savepoint permite desfazer títulos, clientes e eventos financeiros do lote e, ao mesmo tempo, conservar o diagnóstico da rejeição. O custo é rejeitar também as linhas válidas de um lote conflitante; o operador precisa corrigir e reenviar o arquivo.

Uma alternativa plausível seria deduplicar pelo hash do arquivo: é menor, mas não reconhece as mesmas dívidas quando a ordem das linhas muda. Renomear sem alterar os bytes, por outro lado, manteria esse hash. Outra seria aceitar apenas as linhas boas; isso exigiria um contrato de importação parcial que esta aplicação não oferece. Não são alternativas que afirmo ter testado historicamente.

[Captura histórica completa: Lote sintético de dois títulos totaliza R$ 125 e consta como confirmado](screenshots/restore-proof/11adf9df35ba4314945ffdd4fbaeabfc/01-lote-confirmado.png)

_Prova visual histórica `11adf9df…`: fixture separada de R$ 50 + R$ 75, não o CSV de R$ 2.000 acima. A [conferência no banco](restore-proof.md#o-que-foi-conferido) verificou que o reenvio manteve dois títulos e R$ 125; a captura isolada não prova idempotência. [Abrir no tamanho original](screenshots/restore-proof/11adf9df35ba4314945ffdd4fbaeabfc/01-lote-confirmado.png)._

[Captura histórica completa: Conflito no título de R$ 50 junto de um título novo leva à rejeição do arquivo de R$ 150](screenshots/restore-proof/11adf9df35ba4314945ffdd4fbaeabfc/02-conflito-sem-alteracao-financeira.png)

_Mesma execução e viewport: R$ 51 tentam substituir R$ 50, junto de R$ 99 novos. Os R$ 150 são o total do arquivo rejeitado; o banco permaneceu em R$ 125 e o título de R$ 99 não foi gravado. “Novo” descreve a análise da linha, não uma inclusão confirmada. [Imagem completa](screenshots/restore-proof/11adf9df35ba4314945ffdd4fbaeabfc/02-conflito-sem-alteracao-financeira.png)._

Código: [`imports.py`](../backend/src/gestao_recebiveis/imports.py), funções `analyze` e `confirm_batch`; restrições em [`models.py`](../backend/src/gestao_recebiveis/models.py). Provas: `test_repeat_reorder_and_renamed_no_duplicate`, `test_error_last_line_and_conflict_atomic`, `test_preview_revalidated` e `test_concurrent_imports_identical_and_conflicting`, em [test_financial.py](../backend/tests/test_financial.py).

## Uma resposta perdida não pode duplicar o pagamento

Depois de clicar em pagar, perder a conexão não informa se a baixa foi gravada. Impedir um segundo clique ajuda a interface, mas não resolve a repetição da requisição ou dois operadores atuando juntos.

A documentação [Idempotent requests, da Stripe](https://docs.stripe.com/api/idempotent_requests) (consulta: 22/09/2026), consultada em 22/09/2026, descreve repetição após erro de conexão usando a mesma chave e recusa quando os parâmetros mudam. Este projeto reproduz esse risco na baixa integral: compara título e observação e recupera o pagamento persistido. Não integra Stripe nem implementa seu cache de respostas ou sua política de expiração de chaves.

Implementei `pay` para serializar a chave idempotente: ele confere o conteúdo associado e bloqueia o título antes de mudar seu estado. A baixa e o cancelamento das pendências pertencem à mesma transação.

**Exemplo:** para o mesmo título, repetir `{"idempotency_key":"pagamento-demo-01","note":"Conferido"}` devolve o mesmo pagamento. O pedido não contém valor: a API usa o valor integral do título. Reutilizar essa chave com outra observação gera conflito 409. O valor vem do título bloqueado: o cliente não escolhe um valor menor para fazer uma baixa parcial.

**Por que assim:** a decisão financeira fica no servidor e no banco. Centavos inteiros evitam erro de ponto flutuante: a fixture de R$ 0,01 + R$ 0,10 + R$ 10,20 soma exatamente 1.031 centavos. O escopo integral simplifica a regra, mas não atende parcelamento, estorno ou conciliação bancária.

Desabilitar o botão enquanto envia seria uma proteção de interface, mas não cobriria repetição HTTP nem concorrência; por isso a decisão é confirmada no banco. A [captura da baixa de R$ 50](restore-proof.md#capturas-da-mesma-execução) mostra o estado, enquanto os testes abaixo verificam identidade e quantidade de pagamentos.

Código: [`receivables.py`](../backend/src/gestao_recebiveis/receivables.py), `pay`; [`import_csv.py`](../backend/src/gestao_recebiveis/import_csv.py), `cents`. Provas: `test_payment_idempotency_cancel_and_totals`, `test_exact_cents` e `test_concurrent_same_payment_and_cancel_race`, em [test_financial.py](../backend/tests/test_financial.py).

## Tentar enviar e entregar são fatos diferentes

Uma falha de rede depois da aceitação do provedor deixa o resultado desconhecido. Criar uma tentativa nova imediatamente pode repetir a mensagem. Também é possível um worker atrasado voltar depois de outro ter recuperado o job.

Separei a intenção (`Reminder`), a tentativa autorizada (`Attempt`) e a entrega aceita (`Delivery`). O worker toma posse por lease e token crescente. Se perde a posse, não pode concluir o trabalho com um token antigo. Resultado desconhecido exige reconciliação da mesma tentativa e chave.

**Exemplo:** no cenário de resposta perdida, o provedor fictício persiste uma entrega antes de perder a resposta. Após recuperação, a tentativa termina com sucesso e continua havendo uma entrega. A [prova de reinício](demo.md#teste-de-reinício-isolado-em-58-minutos) interrompe o processo e reinicia um PostgreSQL descartável para conferir essa recuperação.

**Por que assim:** manter a fila no PostgreSQL permite coordenar autorização, pagamento e cancelamento com a mesma ordem de locks. A chamada do provedor ocorre fora da transação de autorização, para não manter locks durante a espera externa. Em troca, é necessário representar o resultado desconhecido e reconciliá-lo. Uma baixa impede autorizações futuras, mas não desfaz uma autorização anterior já em trânsito.

[Captura histórica completa: Tentativa número 1 concluída e entrega simulada número 1 preservada após reconciliação](screenshots/restore-proof/11adf9df35ba4314945ffdd4fbaeabfc/03-mesma-tentativa-reconciliada.png)

_Captura histórica da mesma prova: o token de posse mudou, mas a identidade da tentativa e da entrega foi preservada. O [manifesto e as consultas](restore-proof.md) sustentam essa afirmação; não houve envio externo. A nova composição visual não foi executada nessa revisão histórica; sua prova posterior está no [CI do commit `5718cdad`](https://github.com/arthurjoanes/gestao-recebiveis/actions/runs/35744528178) e na [matriz do frontend](frontend-quality.md)._

Um broker seria uma alternativa para distribuir a fila. Ele acrescentaria um serviço e uma fronteira de consistência entre banco e mensageria; manter PostgreSQL simplifica este laboratório, mas exige cuidar de contenção e da rotina de posse/reconciliação. Não medi qual alternativa atenderia melhor uma carga de produção.

Código: [`reminders/service.py`](../backend/src/gestao_recebiveis/reminders/service.py), `claim`, `authorize`, `renew` e `finish`; [`provider.py`](../backend/src/gestao_recebiveis/reminders/provider.py). Provas: [test_reminders.py](../backend/tests/test_reminders.py) e [persistence_probe.py](../backend/tests/persistence_probe.py). O fake usa o mesmo PostgreSQL: essa prova não garante entrega única em um provedor externo.

## O saldo aberto não é o caixa recebido no período

Vencimento e pagamento respondem perguntas diferentes. Um título vencido no mês passado pode ter sido pago hoje. Filtrar tudo pelo vencimento esconderia esse recebimento.

**Exemplo:** ao consultar vencimentos futuros, o saldo aberto respeita esse recorte; o recebido continua usando seu próprio período de pagamento. A interface identifica os dois filtros. O relógio comercial da demonstração altera datas de negócio, enquanto sessão, lease e retry usam tempo real.

Código: [`reporting.py`](../backend/src/gestao_recebiveis/reporting.py) e [`clock.py`](../backend/src/gestao_recebiveis/clock.py). A separação é conferida por `test_midnight_and_received_period_independent_of_due_filter`, em [test_financial.py](../backend/tests/test_financial.py).

## A interface deve conservar o contexto da conferência

Na interface, implementei o contexto de lista e detalhe porque o operador precisa comparar linhas, abrir um detalhe e continuar de onde saiu. A carteira dá prioridade à tabela; importações separam arquivo, conferência e confirmação; lembretes aproximam fila e tentativas. Estados e textos apresentam o que o servidor registrou, sem confundir processamento com entrega.

Ao voltar de um título, os filtros e a página são preservados e o foco volta ao título, quando ele ainda pertence ao recorte. Se a carteira mudou e a página ficou vazia, há uma ação explícita para voltar à primeira página. O detalhe do lembrete conserva a lista montada para manter busca, página e rolagem.

Código: [`workspace.tsx`](../frontend/src/features/workspace.tsx), [`receivables.tsx`](../frontend/src/features/receivables.tsx) e [`reminders.tsx`](../frontend/src/features/reminders.tsx). Jornadas: [journey.spec.ts](../frontend/tests/journey.spec.ts). Resultados executados e limitações: [verificação](verification.md).

## Recuperar também a identidade dos efeitos

Depois de restaurar um backup, a aplicação precisa reconhecer uma baixa repetida e uma tentativa cuja resposta se perdeu. A [prova em outro volume](restore-proof.md) conferiu todas as tabelas e sequências antes de repetir a baixa e reconciliar o envio: preservou pagamento #1, tentativa #1 e entrega simulada #1. O token antigo perdeu a posse. Isso relaciona o mecanismo à consequência financeira observada, sem tratar um backup existente como recuperação automaticamente validada. O provedor simulado está no mesmo banco; o [contrato para integração externa](provider-integration-plan.md) continua proposto.
