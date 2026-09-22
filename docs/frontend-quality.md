# Qualidade da interface financeira

Esta revisão parte do commit `a86db5574d3011415b8c42aa34c03a3e40ee1686`. O candidato reorganiza o Resumo, o detalhe e os filtros da carteira. **A implementação tem lint, tipos e build aprovados; a nova interface não foi executada no navegador.** A primeira inicialização do frontend foi recusada pela revisão automática de comandos, com `blocked by policy`. Não houve repetição, troca de porta ou método alternativo. Capturas comparáveis e jornadas continuam sem verificação; este candidato não tem aprovação visual para publicação.

## Inventário e decisões que cada tela apoia

| Tela ou estado | Pessoa e decisão | Informação indispensável / ação |
|---|---|---|
| Login, carregamento inicial e sessão expirada | Operador ou leitor inicia/retoma a consulta | Perfil, credenciais demo, erro explícito; entrar sem ocultar a distinção entre os papéis |
| Resumo e filtros de período | Financeiro separa dívida de recebimento | Aberto, vencido, em dia e recebido; datas e busca aplicadas; abrir o respectivo recorte |
| Títulos, página seguinte, vazio e página esvaziada | Financeiro localiza uma obrigação | Código + sistema, cliente, vencimento, valor e situação; filtrar, abrir e voltar à mesma página |
| Título aberto, pago ou cancelado | Operador confere antes de dar baixa; leitor consulta | Uma identidade, valor e situação juntos; pagamento/histórico; ação apenas se aberto e operador |
| Confirmação de baixa/cancelamento, erro e envio em curso | Operador confirma uma mudança financeira | Valor integral, consequência, motivo válido; bloqueio durante envio, Escape e foco de retorno |
| Importações, prévia, conflito, confirmação e histórico | Operador confere o lote; leitor consulta resultados | Contagens, total, linha e erro; confirmar apenas lote elegível, sem inclusão parcial |
| Lembretes, seleção e tentativas | Financeiro distingue fila, tentativa e entrega simulada | Estado, etapa, próxima tentativa, horários e identidade; abrir/fechar preservando o recorte |
| Demonstração e controles indisponíveis | Pessoa avaliadora reproduz cenários fictícios | Relógio comercial separado do real, pausa, cenário e papel; não representa envio externo |
| Navegação, menu e conta | Ambos os perfis mudam de área e saem | Área atual, perfil, nome acessível, foco e erro de logout |

Carregamento, ausência de dados, erro de consulta e valor zero são estados diferentes. Atualizar refaz a consulta; a data comercial não é apresentada como horário de atualização da página.

## Referências e interpretação

- [Carbon — uso de tabelas](https://carbondesignsystem.com/components/data-table/usage/): tabela como área de trabalho, controles próximos e números comparáveis. A carteira desktop já atende essa direção; foi preservada em vez de transformada em cartões.
- [Stripe — gestão de faturas](https://docs.stripe.com/invoicing/dashboard): situação e ações vinculadas ao documento financeiro. Adotamos essa proximidade no detalhe; não copiamos código, identidade, cobrança externa ou integrações.
- [Vercel — Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines/blob/main/command.md), consultadas em 22/09/2026: foco visível, formulários sem surpresa, semântica, estados e movimento reduzido. O processo inclui revisão estática; não equivale a teste com tecnologia assistiva.
- [WCAG 2.2 — reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) e [alvo mínimo](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html): referências para 320 CSS px, rolagem restrita à tabela e alvos de interação. Não houve certificação de conformidade.
- [React — estado de componentes](https://react.dev/learn/choosing-the-state-structure) e [efeitos de consulta](https://react.dev/reference/react/useEffect#fetching-data-with-effects): recorte aplicado separado do formulário e descarte de respostas antigas. Não foi criada cache compartilhada entre sessões.

São fontes primárias de padrões e produtos, não estudos de aprovação deste frontend por usuários. A melhora esperada de comparação e alcance da ação é uma inferência de design, ainda sem teste de usabilidade.

## Diagnóstico antes / intervenção

| Evidência no baseline | Impacto / prioridade | Intervenção do candidato | Como validar |
|---|---|---|---|
| `overview.tsx`: vencido, em dia e recebido dentro de `details` fechado; [captura histórica](img/resumo.png) | Comparar os saldos exige descobrir um controle secundário; P1 | Quatro valores simultâneos, composição do aberto explícita e recebido com período próprio | Conferir os quatro valores contra `/overview`, inclusive zero; nova regressão preparada |
| `receivable-detail.tsx`: cliente/código/sistema repetidos antes do valor; [captura histórica](img/titulo.png) | Leitura mais longa e baixa afastada do valor; P2 | Identidade uma vez; valor, situação, vencimento e ações no mesmo bloco | Aberto/pago/cancelado, valores longos, leitor, confirmação e retorno de foco |
| `receivables.tsx`: quatro campos sempre expostos no mobile | Resultados deslocados pela edição do recorte; P2 | Até 900 px, botão de filtros com `aria-expanded`/`aria-controls`; recorte aplicado continua visível | 320/390/768, teclado, envio válido recolhe e devolve foco; erro permanece aberto |
| CSS mobile escondia o sistema de origem junto à descrição | Códigos iguais de sistemas distintos ficam ambíguos; P1 | Origem permanece na linha compacta; descrição completa continua no detalhe | Comparar títulos com mesmo código de sistemas distintos |
| Bordas de campos muito claras e foco único também sobre cabeçalho escuro | Contorno/foco podem perder contraste; P2 | Borda `#7a899e`, foco azul na superfície clara e claro no navy | Cálculo dos pares + inspeção real de todos os estados, ainda pendente |
| Layout tinha max-width de 1500 px e composição verde | Preferência e escala não alinhadas à direção financeira aprovada; P3 | Max-width 1440 px centrado, navy/azul, mesma grade e escala entre áreas | Capturas controladas até 2560 px e com ampliação |
| Estilos de disclosure/identidade duplicada deixariam de ter consumidor | Complexidade sem comportamento útil; P3 | Removidos `balance-details`, `metric-breakdown`, `invoice-caption`, `invoice-identity`, `separator` e `count-pill` | Busca nas fontes, diff, lint e build |

Não foi encontrado P0 na inspeção das fontes. Isso não exclui regressões visuais ou funcionais que o navegador ainda precisa verificar.

## Matriz das 11 dimensões

Cada célula mostra **antes → depois**. C = Conforme no escopo da inspeção de fontes; P = Parcialmente conforme; NC = Não conforme; NV = Não verificado; NA = Não aplicável. O estado C documental/estático não implica conformidade visual, teste de usuário ou WCAG integral. “Depois” se refere ao candidato, não a uma publicação.

| Dimensão | Login | Resumo | Carteira | Detalhe + confirmação | Importações + prévia | Lembretes + tentativas | Demo | Navegação + conta |
|---|---|---|---|---|---|---|---|---|
| 1. Objetivo e público | C→C | C→C | C→C | C→C | C→C | C→C | C→C | C→C |
| 2. Hierarquia da informação | C→C | NC→P | P→P | P→P | C→C | C→C | C→C | C→C |
| 3. Layout, alinhamento, espaçamento, densidade | P→NV | NC→NV | P→NV | P→NV | P→NV | P→NV | P→NV | P→NV |
| 4. Tipografia, cores e consistência | P→P | P→P | P→P | P→P | P→P | P→P | P→P | P→P |
| 5. Indicadores, gráficos e tabelas | NA→NA | P→P | P→P | C→C | C→C | C→C | C→C | NA→NA |
| 6. Navegação, filtros, formulários e ações | P→NV | P→NV | P→NV | P→NV | P→NV | P→NV | P→NV | P→NV |
| 7. Carregamento, vazio, erro e atualização | C→P | C→P | C→P | C→P | C→P | C→P | C→P | C→P |
| 8. Acessibilidade e responsividade | P→NV | P→NV | P→NV | P→NV | P→NV | P→NV | P→NV | P→NV |
| 9. Desempenho | P→P | P→P | P→P | P→P | P→P | P→P | P→P | P→P |
| 10. Manutenção e reaproveitamento | C→C | C→C | P→C | P→C | C→C | C→C | C→C | C→C |
| 11. Dados, regras e permissões | C→C | C→C | C→C | C→C | C→C | C→C | C→C | C→C |

NA na dimensão 5: login e navegação não apresentam informação analítica ou tabela. Os outros casos foram avaliados quanto aos números/tabelas existentes; não há justificativa para adicionar gráficos decorativos.

P na hierarquia nova: o DOM entrega os dados na ordem proposta, mas faltam renderização e observação de uso. P em estados: ramificações e proteção contra resposta antiga permanecem, porém não foram percorridas novamente. P em desempenho: assets de build foram comparados, mas waterfall, paint, renderizações e interação não foram medidos. P nas cores: pares principais calculados; estados sobrepostos e todos os componentes não foram auditados visualmente.

## Composição, contratos e custo

As superfícies usam `#f3f6fa`/branco, texto `#172b49`, texto secundário `#526176`, ação `#1e57a4` e cabeçalho `#142b49`. Verde fica reservado a resultados positivos; âmbar e vermelho mantêm rótulos textuais de estado. A fonte é a pilha local Segoe UI/Arial, sem download. Valores usam algarismos tabulares e continuam passando por `money`, com `BigInt`: centavos acima da precisão de `Number` não são convertidos em ponto flutuante.

O conteúdo ocupa até 1440 px, centralizado, com margens internas de 36/24/16 px. O Resumo usa quatro colunas, duas até 1050 px e uma até 480 px. Nenhum saldo depende de accordion. O recebido não é parte do aberto e mantém as datas efetivas retornadas pela API. O recorte de vencimento continua aplicado apenas à carteira; a busca alcança carteira e recebimentos conforme o contrato existente.

`ResponsiveFilters` mantém a mesma instância dos campos ao recolher; a edição não altera a consulta antes de enviar. Abaixo do breakpoint, envio válido fecha os controles e foca o botão; erro de período não fecha nem troca resultados. Desktop conserva os controles visíveis. Não há efeito de resize, leitura de layout durante render, biblioteca de UI nova, armazenamento de filtros financeiros em URL/localStorage ou cache global.

`useResource`, transporte, tipos, regras e guard de retorno da carteira permanecem inalterados. Consultas independentes do Resumo continuam iniciadas em paralelo. Listas paginadas e prévias de 50 linhas limitam o DOM; não foi adicionada virtualização sem medição. A importação ainda pode trazer até 5.000 linhas no relatório da API: paginação de render não reduz esse payload. Não há alegação de desempenho em carteiras maiores.

Hover/foco usam transições de cor de 150 ms; entrada de título usa 180 ms e desaparece com `prefers-reduced-motion`. A confirmação usa dialog nativo, limite de altura e rolagem interna. Não há animação contínua além do indicador de carregamento, também coberto pela preferência de movimento reduzido.

## Provas executadas e o que falta

O [registro de verificações estáticas](evidence/frontend-quality-static-20260922.json) contém base, hashes, resultados e limites. Nesta revisão passaram ESLint, Prettier, TypeScript, build padrão de produção e listagem dos 15 casos da suíte Playwright. Listagem não é execução. Também passaram dez asserções isoladas de formatação e nove pares de contraste: seis pares de texto acima de 4,5:1 e três de contorno/foco acima de 3:1. Isso não substitui navegador.

Os chunks JS/CSS emitidos somam 651.583 bytes no baseline e 651.944 no candidato; comprimidos individualmente com gzip, 193.093 e 193.251 bytes. O aumento é de 361 bytes sem compressão e 158 comprimidos, sem nova dependência. Esses totais de build não são uma medição de transferência, cache, velocidade de tela ou interação. A comparação de conteúdo normalizado também confirmou 68 arquivos protegidos sem alteração, incluindo backend, dados, cliente HTTP, tipos, formatação, hook de consulta e navegação da área de trabalho.

Antes do bloqueio, a API da demo foi consultada com banco próprio descartável: 240 títulos, 192 abertos, 96 vencidos, 96 em dia e 48 pagamentos. Em 17/08/2026: aberto **R$ 515.153,87**, vencido **R$ 243.020,08**, em dia **R$ 272.133,79**, recebido de 01 a 17/08 **R$ 117.816,83**. Essa é evidência da API, não uma captura da tela. O banco e os demais recursos próprios foram encerrados; nenhuma carteira de outra tarefa foi usada.

As imagens atuais em `docs/img/` são históricas e foram preservadas. A captura anterior de Resumo contém totais após outras jornadas e não corresponde ao seed acima; não deve ser usada como par comparativo deste candidato. Não foram criados screenshots fictícios ou imagens substitutas.

Para fechar a revisão, executar o candidato e um baseline do commit indicado com a mesma fixture, perfil, relógio e recortes. Capturar login, Resumo, carteira, título aberto/pago/cancelado, confirmação, importação/prévia/conflito, fila/tentativas e demo em **1440×900, 1366×768, 768×1024, 390×844 e 320×844**; repetir recorte `TIT-0001`, vencimento 18/07/2026, status vencido nos dois lados. Registrar wide 2560 px, zoom nativo 200%, teclado e movimento reduzido separadamente. Capturas de erro/loading devem identificar respostas controladas.

A suíte preparada mantém importação, precisão, permissões, falhas, cancelamento, fila, retorno à página e proteção de foco durante resposta atrasada. Acrescenta regressão do recorte compacto e mantém os quatro valores do Resumo visíveis sem abrir disclosure. **Todas as jornadas de navegador do candidato, capturas comparáveis, medição de overflow, foco executado, leitor de tela e desempenho de interação permanecem Não verificados.** O resultado histórico de 14 testes não foi atribuído a este código.
