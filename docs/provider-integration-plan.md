# Integrar um provedor sem duplicar efeitos

**Problema central:** após perder uma resposta, o sistema precisa distinguir uma mensagem não enviada de uma mensagem já aceita. Restaurar o PostgreSQL não desfaz uma entrega que ocorreu fora dele.

Este é um plano de integração, não um adaptador implementado. Nenhum fornecedor ou sandbox foi escolhido; nenhuma mensagem foi enviada a um destinatário real. A [implementação atual](../backend/src/gestao_recebiveis/reminders/provider.py) simula o provedor e guarda seu resultado no mesmo PostgreSQL da aplicação.

## 1. Descobrir o contrato antes de programar o adaptador

| Informação necessária                                                          | Por que muda a solução                                                     |
| ------------------------------------------------------------------------------ | -------------------------------------------------------------------------- |
| Chave de idempotência: escopo, validade e comportamento com conteúdo diferente | Define se uma repetição pode recuperar a mesma operação ou criar outra     |
| Consulta por chave ou ID e estados possíveis                                   | Permite investigar uma resposta perdida sem despachar de novo              |
| Significado de aceito, enviado e entregue                                      | Evita apresentar uma aceitação técnica como recebimento pelo cliente       |
| Callbacks: autenticação, repetição e ordem                                     | Exige validar a origem e tratar o mesmo evento sem duplicar mudanças       |
| Timeout, cancelamento e limites de requisição                                  | Interromper a espera local não confirma que o provedor cancelou o trabalho |
| Retenção do histórico externo e exportação para conciliação                    | Determina o que pode ser reconstruído após restaurar um backup antigo      |

Preencher essa tabela com documentação oficial e resultados do sandbox escolhido. Campo desconhecido continua desconhecido; não presumir que todo serviço tem essas capacidades.

## 2. Preservar o resultado financeiro e a identidade da tentativa

Manter a autorização transacional antes da chamada externa e a conclusão em outra transação. Preservar o vínculo título → lembrete → tentativa → chave/resultado externo. Registrar a classificação do resultado sem guardar segredos nem o conteúdo pessoal completo nos logs.

Uma resposta incerta conserva a tentativa para reconciliação. Só liberar novo despacho quando o contrato e a evidência sustentarem essa decisão. A baixa confirmada impede novas autorizações, mas não desfaz o envio anteriormente autorizado. Se o fornecedor não permitir resolver a incerteza com segurança, a solução pode exigir revisão manual, em vez de repetir automaticamente.

## 3. Ensaios de aceite no sandbox

| Cenário                                           | Evidência necessária                                                                  |
| ------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Mesma chave e conteúdo repetidos                  | Identidade externa e efeito observável iguais, conforme o contrato                    |
| Mesma chave com outro conteúdo                    | Recusa identificável, sem substituir a operação anterior                              |
| Falha antes do despacho                           | Nenhuma aceitação externa; tentativa local classificada corretamente                  |
| Resposta perdida depois da aceitação              | Reconciliação da tentativa original sem segunda entrega observada                     |
| Dois workers e posse antiga                       | Somente a posse válida conclui o estado local; efeito externo conferido separadamente |
| Callback repetido ou atrasado, se existir         | Estado válido preservado e evento aplicado de forma idempotente                       |
| Restore de corte anterior a uma aceitação externa | Reconciliação com o histórico atual do provedor antes de retomar envios               |

Registrar versão do adaptador, contrato consultado, ambiente, horários, IDs sanitizados, passos, resultados e falhas. Um teste local com fake continua útil para regressão, mas não substitui esses ensaios. Não é necessário executar uma campanha com clientes para testar o contrato.

## 4. Recuperação fora do computador

O procedimento futuro precisa de cópia protegida em local independente, destino vazio, credenciais e versão de schema compatíveis. Antes de abrir a carteira, comparar IDs, valores, pagamentos, auditoria e sequências. Antes de reativar lembretes, reconciliar as tentativas com o estado externo atual.

Registrar separadamente a idade do corte recuperado e o tempo até a operação validada. Só depois definir frequência de backup e metas de recuperação coerentes com o volume e a operação. O ensaio em outro volume do mesmo host não comprova esse cenário.

## Código e evidências relacionados

[worker](../backend/src/gestao_recebiveis/worker.py).
