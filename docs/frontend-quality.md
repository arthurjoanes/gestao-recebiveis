# Qualidade da interface

Este guia descreve os contratos de navegação, estados e acessibilidade do frontend. Regras financeiras e permissões são validadas no servidor; a interface apresenta os dados e preserva a intenção de cada ação.

## Valores e estados financeiros

O Resumo distingue o saldo aberto, suas partes vencida e em dia, e os recebimentos do período. Filtros de vencimento e de pagamento têm efeitos diferentes e são identificados junto aos valores. Títulos e relatórios exibem original, recebido e saldo, com centavos completos.

Valores monetários usam centavos inteiros e formatação com `BigInt`. Situação, erro e sucesso são identificados por texto, além da cor. Carregamento, ausência de dados, falha de consulta e valor zero têm mensagens distintas.

A confirmação de recebimento reúne título, cliente, valor a registrar e saldo resultante. **Quitar saldo restante** envia explicitamente o valor conferido; uma alteração concorrente pode exigir consultar o saldo e criar uma nova intenção. Intenções antigas sem valor explícito conservam seu payload original durante o replay. Consulte o [contrato HTTP](api-contract.md) e as [regras da evolução](evolucao-20261012.md).

## Sessão e recuperação

- Logout retira o conteúdo protegido imediatamente e limpa intenções locais, mesmo se a resposta da API se perder.
- Respostas de uma sessão anterior são descartadas. Consultas substituídas são canceladas e não atualizam o novo recorte.
- Um 403 revalida identidade, perfil e CSRF. Perda de permissão retira os controles de alteração.
- Timeout, resposta inválida ou perda de conexão após pagamento conservam chave e conteúdo para recuperação; a interface não cria automaticamente outro recebimento.
- O leitor consulta os dados sem controles de pagamento, cancelamento ou configuração da demo.

O estado de autenticação do cliente pertence ao navegador. A renderização no servidor usa um estado inicial vazio, sem compartilhar credenciais ou identidade entre requisições.

## Navegação e formulários

Busca, filtros, página e registro selecionado permanecem ao abrir e voltar de títulos, aging, extrato e tentativas de lembrete. O retorno restaura o foco no acionador; uma resposta atrasada não move o foco de quem já está digitando.

Diálogos têm nome acessível, foco inicial, navegação por Tab e Shift+Tab, fechamento por Escape e retorno ao acionador. Durante envio, controles impedem nova confirmação. Mensagens de erro ficam próximas do campo, e validação inválida direciona o foco à entrada correspondente.

Datas de vencimento e recebimento são agrupadas separadamente. Cada paginação tem nome próprio; a impressão do extrato identifica filtros e página exibida, enquanto os totais abrangem o recorte completo.

## Responsividade e acessibilidade

A carteira e os títulos dos relatórios reorganizam suas linhas até 1100 px para manter saldo, situação e identidade visíveis. O menu e os filtros móveis recolhem até 900 px; aplicar filtro altera a consulta somente no envio. Tabelas extensas de importações e histórico mantêm rolagem local identificada.

Confira pelo menos 320, 390, 768, 1024 e 1440 CSS px, incluindo nomes longos, valores altos, vazio, erros e diálogo aberto. Teste teclado, foco visível, texto ampliado e preferência por movimento reduzido. Não dependa apenas de uma varredura automática para contraste ou semântica.

IBM Plex Sans 400/600 é servida localmente com `next/font/local`, `display: swap` e fallback Arial. Preserve a [licença OFL 1.1](../frontend/src/app/fonts/plex-LICENSE.txt) e os [registros de origem](../frontend/src/app/fonts/sources.json).

## Testes e manutenção

Execute o comando [documentado de verificação](verification.md#reproduzir-a-verificação-local). Build, ESLint, Prettier e TypeScript fazem parte das verificações do frontend.

| Suíte | Cobertura principal |
| --- | --- |
| [journey.spec.ts](../frontend/tests/journey.spec.ts) | Importação, conflitos, lembretes, perfis, filtros, paginação e retorno de foco |
| [payments-reports.spec.ts](../frontend/tests/payments-reports.spec.ts) | Parcelas, recuperação, aging, extrato e impressão |
| [session-safety.spec.ts](../frontend/tests/session-safety.spec.ts) | Logout, troca de conta, respostas atrasadas e revogação de acesso |
| [uiux-financial.spec.ts](../frontend/tests/uiux-financial.spec.ts) | Valor confirmado, intenção legada e timeout de pagamento |
| [uiux-accessibility.spec.ts](../frontend/tests/uiux-accessibility.spec.ts) | Axe, reflow, texto ampliado, movimento reduzido e percurso em Firefox |

A validação local de 12/10/2026 aprovou 37 casos, sem skip ou retry. Os [resultados e limites](verification.md#sessão-confirmação-e-reflow--12102026) identificam as versões e verificações realizadas. Zoom nativo, leitor de tela, produtividade com usuários e desempenho de produção não foram demonstrados; os testes não certificam conformidade WCAG integral.

Referências técnicas: [WCAG 2.2](https://www.w3.org/TR/WCAG22/), [APG: diálogo modal](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) e [Playwright: acessibilidade](https://playwright.dev/docs/accessibility-testing).
