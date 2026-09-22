# Qualidade da interface financeira

Direção visual de 22/09/2026 sobre o commit `bd5aeb1c11d3fa2e98a4e401aa3e86b22e2945f4`. O baseline já tinha carteira, detalhe, filtros compactos e os quatro saldos visíveis. A nova composição separa **posição da carteira**, **movimentação recebida** e **conferência de títulos**, com marca e tipografia próprias.

**Design aprovado pelo autor em 22/09/2026; execução automatizada comprovada no commit `5718cdad3c5052ddbf6f660797121e9c47aa46c8`:** o [CI do commit `5718cdad`](https://github.com/arthurjoanes/gestao-recebiveis/actions/runs/35744528178) aprovou 15 casos Playwright (14 jornadas interativas e 1 caso de formatação BRL), sem skip ou retry, e produziu 21 PNGs. A revisão local anterior aprovou lint, tipos, build e verificações estáticas; o lançamento foi recusado com `blocked by policy` e não foi repetido nem contornado. O CI posterior é uma prova remota distinta. O [recibo do CI](evidence/frontend-ci-20260922.json), o [registro da direção](evidence/visual-direction-static-20260922.json) e a [revisão anterior](evidence/frontend-quality-static-20260922.json) conservam seus escopos e fontes.

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

## Diagnóstico e duas alternativas antes de expandir

As prioridades indicam o impacto do problema no baseline: P1 compromete a compreensão da tarefa; P2 representa atrito de leitura; P3 é refinamento visual. A linha de preservação não registra um defeito. A validação abaixo distingue inspeção estática, jornadas remotas no SHA publicado e verificações ainda não realizadas.

| Evidência do baseline atual | Efeito sobre a decisão | Prioridade | Intervenção | Validação e limite |
|---|---|---|---|---|
| Quatro saldos lado a lado, com peso semelhante | Recebido parece uma parcela do aberto | P1 | Aberto ocupa a largura de seu grupo; vencido e em dia aparecem abaixo como partes. Recebido ocupa superfície separada com período e ressalva explícita | [Fonte do Resumo](../frontend/src/features/overview.tsx) conserva os quatro valores da API e explicita as relações. CI aprovou visibilidade dos quatro saldos, recortes e ausência de overflow nas cinco larguras da suíte; confronto visual pareado com o baseline permanece não verificado |
| Carteira já apresenta código/origem, cliente, vencimento, valor e situação juntos | Tabela sustenta conferência real | Não aplicável: preservação | Preservar tabela e filtros aplicados; não trocar títulos por cartões | [Fonte da carteira](../frontend/src/features/receivables.tsx) mantém campos e paginação. CI aprovou filtros, retorno à página e foco, inclusive resposta atrasada sem roubar a digitação |
| Detalhe já reúne valor, situação e baixa | Proximidade correta, mas superfície igual às demais | P2 | Borda de identificação do registro e separação entre decisão financeira e metadados; mesmas ações e permissões | Inspeção de fontes preserva ações e papéis. CI aprovou detalhe com dados longos nas cinco larguras, confirmação e retorno de foco; não é estudo de leitura com pessoas |
| Ícone quadrado genérico e fonte de sistema | Produtos diferentes pareciam o mesmo shell | P3 | Símbolo original derivado do R/coluna de registros, IBM Plex Sans e cabeçalho navy | SVGs/fontes e amostras 16/24/32 px inspecionados estaticamente. Carregamento, fallback e favicon na aplicação: não verificados |

As duas propostas usam **os mesmos dados** da demo já consultada: referência 17/08/2026, aberto R$ 515.153,87 (192 títulos), vencido R$ 243.020,08 (96), em dia R$ 272.133,79 (96), recebido de 01 a 17/08 R$ 117.816,83 (48). Não são indicadores novos.

- [Proposta A — posição e movimento](design/proposta-a.png) ([SVG](design/proposta-a.svg)): agrupa partes do aberto e separa recebimentos. **Escolhida** pela relação explícita entre os valores e pelo acesso direto à lista vencida.
- [Proposta B — conferência primeiro](design/proposta-b.png) ([SVG](design/proposta-b.svg)): lista ocupa o lado principal, saldos formam uma coluna lateral. Rejeitada porque enfraquece a leitura do todo e das partes no Resumo.

Ambas são **simulações de composição**, identificadas dentro da imagem; não são screenshots nem prova de responsividade. A escolha orienta a implementação e continua sem estudo de usabilidade. A pesquisa rejeitou aparência editorial bege/serifada e filetes decorativos.

## Referências e tradução para o produto

[Stripe — gestão de faturas](https://docs.stripe.com/invoicing/dashboard), em imagem oficial, mostrou valor/situação/ação vinculados ao documento. Foi aproveitada a proximidade para conferência, sem cobrança externa, integração ou cópia. A captura do [SolidInvoice](https://github.com/SolidInvoice/SolidInvoice) consultada anteriormente reforçou a lista de trabalho; seus cartões coloridos equivalentes e colunas comprimidas foram rejeitados. Nenhum código desses produtos foi incorporado; suas licenças não são tratadas como licença geral de dependências ou imagens.

| Fonte primária / material visto em 22/09/2026 | Aproveitado e adaptado | Rejeitado / licença |
|---|---|---|
| [Linear — redesenho](https://linear.app/now/how-we-redesigned-the-linear-ui), imagem oficial da interface com lista e detalhe | Contraste entre navegação, edição e conteúdo; cor intensa tem uma função | Não copiar shell, código, marca ou imagem. A publicação não concede licença para reutilizar seus assets |
| [Carbon — tabelas](https://carbondesignsystem.com/components/data-table/usage/) e [eixos/rótulos](https://carbondesignsystem.com/data-visualization/axes-and-labels/) | Alinhamento numérico, unidade e comparabilidade; controles junto do trabalho | Não adicionar gráficos para decorar nem arredondar dinheiro para K/M; padrões consultados, nenhum componente copiado |
| [Atlassian — cor](https://atlassian.design/foundations/color/) e [Radix — escalas](https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale) | Separar fundo, elemento interativo, texto e status | Não adotar as paletas como identidade pronta; sem pacote ou tokens copiados |
| [Pentagram — Galaxy](https://www.pentagram.com/work/galaxy), aplicação real de símbolo e wordmark | Um gesto reconhecível que funciona sem ornamento e em aplicações diferentes | Não reutilizar círculo/quadrado, desenho ou marca; direitos dos autores |
| [Swavee — identidade conceitual](https://www.behance.net/gallery/241721015/Visual-Identity-design-for-Swavee), apresentação dos designers Tobi Victor/Nifemi Adelana | Relação entre nome, símbolo e aplicação; referência fictícia explicitamente identificada | Não copiar letras, esfera, fotos, gradientes ou marketing. Portfólio conceitual não comprova usabilidade nem exclusividade |

As [Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines/blob/main/command.md) foram consultadas em 22/09/2026. Foram aplicados foco visível, redução de movimento, campos nomeados, consulta/aplicação separadas e ausência de dependência visual nova. [Estado em React](https://react.dev/learn/choosing-the-state-structure), [reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) e [alvos](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) orientam decisões; não certificam a aplicação. Estas fontes sustentam padrões e inferências de design, não uma avaliação de usabilidade com usuários.
## Identidade, tipografia e superfícies

O símbolo é um desenho original de coluna de registro ligada à letra R: indica carteira e conferência, sem brasão financeiro genérico. [Wordmark](../frontend/public/brand/wordmark.svg), [compacto](../frontend/public/brand/mark.svg), [mono](../frontend/public/brand/mark-mono.svg), [reverso](../frontend/public/brand/mark-reverse.svg) e [favicon](../frontend/src/app/icon.svg) foram produzidos em SVG. O texto da marca no produto usa a mesma família, com nome acessível e símbolo decorativo. A [conferência a 16/24/32 px](design/marcas-16-24-32.png) preservou R/coluna em rasterização estática; legibilidade na aba real permanece não verificada. Não se alega exclusividade jurídica da marca.

A [comparação tipográfica](design/tipografia.png) usa os arquivos reais transformados em contornos. IBM Plex Sans 400/600 foi escolhida pela diferenciação de dígitos e pela leitura compacta dos registros; Source Sans 3 ficou para o texto analítico da Loja. PT-BR, moeda, sinais e dígitos foram conferidos por FontTools; os dígitos têm avanços iguais por padrão, sem feature `tnum` nos arquivos. O CSS também declara números tabulares. O carregamento real/fallback ainda não foi observado. `next/font/local`, `display: swap` e Arial como fallback não dependem de serviço externo.

Os dois WOFF2 somam **130.080 bytes** antes do transporte/cache, custo novo para a identidade. Não houve medição de LCP ou interação. Fontes IBM Plex no commit `78cd4223d8de9fcb78cba84eadecb269c56093c5`, [origens e hashes](../frontend/src/app/fonts/sources.json), sob [OFL 1.1 integral](../frontend/src/app/fonts/plex-LICENSE.txt), mantidas sem alteração. Código do projeto e fontes têm licenças próprias; nenhum kit de dashboard foi incorporado.

Canvas `#f0f2f5`, registros brancos, cabeçalho `#152c49`, aberto `#1e477f`, recebido `#e8f0ec`: são funções diferentes, não cartões com cor trocada. Verde se refere a recebimento; vencido mantém texto e valor em âmbar. Filtros usam superfície de preparação neutra. A ação é azul, erro mantém vermelho/rótulo. Nove pares principais passaram cálculo isolado de contraste; isso não equivale a conformidade integral.

Conteúdo centrado até 1440 px, margens 36/24/16 px. A posição ocupa duas partes da largura e o recebido uma; até 1050 px, grupos se empilham; até 480 px, vencido/em dia também. O maior número usa `clamp(28px, 3.3vw, 44px)`; os demais preservam centavos e podem quebrar. Carteira desktop continua tabela; filtros recolhem até 900 px sem alterar a consulta antes do envio. Detalhe, confirmação, importação, lembretes e demo compartilham tokens/ritmo sem receber indicadores decorativos. Transições de cor de 150 ms e preferência de movimento reduzido permanecem; foi removida a animação de entrada do título.

## Matriz das 11 dimensões

Cada célula mostra **antes → depois**. C = Conforme no escopo da inspeção de fontes; P = Parcialmente conforme; NC = Não conforme; NV = Não verificado; NA = Não aplicável. O estado C documental/estático não implica conformidade visual, teste de usuário ou WCAG integral. “Depois” se refere à direção implementada em `5718cdad`; a execução remota torna parciais os itens antes não verificados, sem transformar cobertura limitada em conformidade integral.

| Dimensão | Login | Resumo | Carteira | Detalhe + confirmação | Importações + prévia | Lembretes + tentativas | Demo | Navegação + conta |
|---|---|---|---|---|---|---|---|---|
| 1. Objetivo e público | C→C | C→C | C→C | C→C | C→C | C→C | C→C | C→C |
| 2. Hierarquia da informação | C→C | P→P | P→P | P→P | C→C | C→C | C→C | C→C |
| 3. Layout, alinhamento, espaçamento, densidade | P→P | P→P | P→P | P→P | P→P | P→P | P→P | P→P |
| 4. Tipografia, cores e consistência | P→P | P→P | P→P | P→P | P→P | P→P | P→P | P→P |
| 5. Indicadores, gráficos e tabelas | NA→NA | P→P | P→P | C→C | C→C | C→C | C→C | NA→NA |
| 6. Navegação, filtros, formulários e ações | P→P | P→P | P→P | P→P | P→P | P→P | P→P | P→P |
| 7. Carregamento, vazio, erro e atualização | C→P | C→P | C→P | C→P | C→P | C→P | C→P | C→P |
| 8. Acessibilidade e responsividade | P→P | P→P | P→P | P→P | P→P | P→P | P→P | P→P |
| 9. Desempenho | P→P | P→P | P→P | P→P | P→P | P→P | P→P | P→P |
| 10. Manutenção e reaproveitamento | C→C | C→C | P→C | P→C | C→C | C→C | C→C | C→C |
| 11. Dados, regras e permissões | C→C | C→C | C→C | C→C | C→C | C→C | C→C | C→C |

NA na dimensão 5: login e navegação não apresentam informação analítica ou tabela. Os outros casos foram avaliados quanto aos números/tabelas existentes; não há justificativa para adicionar gráficos decorativos.

P na hierarquia nova: o CI renderizou a composição, mas não houve observação de uso com pessoas. P em estados: as jornadas exercitaram erros, vazios, expiração, filtros e proteção de foco; não esgotam todas as combinações. P em layout, navegação e acessibilidade: há checks reais e capturas no escopo da suíte, sem comparação pareada de todas as telas, zoom nativo ou leitor de tela. P em desempenho: assets de build foram comparados, mas waterfall, paint, renderizações e interação não foram medidos. P nas cores: pares principais calculados; estados sobrepostos e todos os componentes não foram auditados visualmente.

## Contratos e verificações

Cliente HTTP, tipos, formatação com `BigInt`, hook de consulta, navegação/foco, backend, auth, papéis e regras ficaram fora do delta. O agrupamento usa os quatro valores retornados, sem somá-los novamente no frontend. O vencido é parte do aberto; recebido mantém suas próprias datas. Importação não passa a permitir inclusão parcial; lembretes continuam simulados; controles do leitor não ganham permissão.

Na revisão local: **ESLint, Prettier, TypeScript e build de produção aprovados; 15 casos Playwright apenas listados**. Dez asserções puras de formatação e nove pares de contraste foram conferidos. O manifesto histórico lista hashes e assets emitidos; bytes de build não medem transferência ou velocidade percebida. Depois, o [CI do commit `5718cdad`](https://github.com/arthurjoanes/gestao-recebiveis/actions/runs/35744528178) executou os **15 casos com sucesso em 33,4 s**: 14 jornadas interativas e 1 caso de formatação, Chromium/Playwright 1.63.0, um worker, zero skip/retry, sem filtro de seleção. As jornadas incluem cinco larguras (1440/1366/768/390/320), dados longos, baixa/importação, papéis, filtros, página/foco, erro e recuperação. As [21 capturas do artefato](https://github.com/arthurjoanes/gestao-recebiveis/actions/runs/35744528178/artifacts/10702621807) pertencem a essa execução; seus estados podem variar conforme os casos modificam a massa. Não foram iniciados recursos locais de aplicação nesta atualização.

As imagens em `docs/img/` continuam históricas. A [captura publicada do Resumo](screenshots/publication-20260922/overview.png) veio do CI `5718cdad`; não forma par controlado com o baseline. Ainda falta comparar baseline/candidato com mesmo seed, perfil, relógio, filtros e recorte `TIT-0001`/vencido/18-07-2026, cobrindo todas as telas do inventário e wide 2560. Zoom nativo de 200%, leitor de tela, fallback/favicon e desempenho percebido continuam não verificados. A aprovação do design e os testes automatizados não comprovam conformidade AA integral ou desempenho em produção.
