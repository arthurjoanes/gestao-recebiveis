# Verificação local

## Auditoria final — 22/09/2026

Base examinada: [`4bb9b57edc1b298cada00bdf9045efb861ed0faa`](https://github.com/arthurjoanes/gestao-recebiveis/tree/4bb9b57edc1b298cada00bdf9045efb861ed0faa), branch `main`, remote `https://github.com/arthurjoanes/gestao-recebiveis.git`, árvore inicialmente limpa. Inventário: 167 arquivos rastreados e nenhum novo; `.env`, instruções locais `AGENTS.md`, dependências, caches e resultados ignorados foram distinguidos dos arquivos publicáveis. Nenhum histórico, imagem ou manifesto foi removido ou atualizado para representar outra versão.

Chamaria o autor para entrevista pelos mecanismos de importação atômica, baixa idempotente, permissões e recuperação de tentativa incerta. Os testes verificam estados financeiros, identidade de efeitos e concorrência, além de respostas HTTP. A fila no mesmo PostgreSQL tem benefício demonstrado: compartilhar a transação entre título, pagamento e cancelamento. O custo é uma máquina de estados que exige manter a ordem dos locks e a reconciliação. Uma pergunta de domínio útil seria explicar a disputa de dois títulos pela mesma chave de pagamento e o que muda quando o provedor externo não volta ao estado de um backup.

Foram inspecionados os contratos, rotas, parser/importação, pagamento, totais e fusos, sessões/admissão, fila/worker, migrações, Dockerfiles, workflows e scripts de prova; asserções de concorrência e falhas foram lidas por amostragem. No frontend, foram revistos consulta/erros, navegação, filtros, detalhe, diálogos e seus testes. Isso não equivale a revisão linha a linha de todos os arquivos.

| Requisito e evidência atual | Situação | Correção ou limite |
| --- | --- | --- |
| Instalação Windows a partir de fontes publicáveis | Conforme após correção P1 | Exportação com `core.autocrlf=true` falhou em 30 arquivos do Prettier; `.gitattributes` agora fixa LF no frontend, preservando fontes binárias/licença. Nova exportação passou lint, tipos e build |
| Regras, dinheiro, datas, permissões e concorrência | Conforme no escopo demo | 158 testes PostgreSQL passaram; valor em centavos, recortes distintos e papéis continuam no servidor. Uma empresa, sem isolamento multiempresa contratado |
| Regressões das guardas de restauração | Conforme após correção P2 | Os 16 testes host passavam localmente, mas não entravam no CI; o workflow agora os executa explicitamente |
| Diagnósticos de navegador preservados | Conforme após correção P2 | Traces/PNGs já usavam volume e upload; relatório HTML era perdido no container removido. Compose normal e de prova agora têm volume próprio para o relatório, incluído no upload do CI |
| Público, problema, entrada, exemplo, decisões, autoria e limites | Conforme na leitura simulada do README | Define título e baixa; distingue a prova de R$ 125 da fixture de R$ 2.000 e da massa visual; remove repetição de CI e justificativa processual; indica manutenção e ajuda. Não houve estudo com leitores |
| Referências, identidade, hierarquia, densidade, foco e estados | Parcial | Fontes primárias e direção existente preservadas; 15 casos Chromium passaram, incluindo cinco larguras e teclado. Quatro capturas atuais foram inspecionadas: Resumo 1440/320, detalhe longo e diálogo 320. Não se certifica AA integral |
| Contexto real e fronteira da simulação | Conforme | [Stripe documenta repetição idempotente](https://docs.stripe.com/api/idempotent_requests); o [caso de baixa](problem-solution.md#uma-resposta-perdida-não-pode-duplicar-o-pagamento) explicita mecanismo próprio e diferenças. Nenhuma integração ou benefício com usuários é presumido |
| Arquivos públicos, dependências e provas históricas | Conforme no escopo do scan | Gitleaks e Trivy descritos abaixo; propostas visuais, capturas antigas, manifestos de falha, migrations e locks mantidos com sua função |
| Restauração integral, produção e acessibilidade assistiva | Não verificado nesta rodada | Guardas e plano executados; não foi repetido o ensaio completo de restore/restart. Provedor externo, perda de host, leitor de tela, zoom nativo e medição de desempenho permanecem fora desta validação |

O achado histórico do README em `5718cdad` já estava corrigido por `1198efd` e `4bb9b57`: a execução remota de 15 casos estava documentada, com limites visuais separados. Não foi tratado como falha atual.

### Execuções desta auditoria

Uma exportação `git archive` recebeu somente o diff candidato, sem `.env`, `node_modules` ou build pessoais. Credenciais temporárias foram geradas fora do repositório. Os serviços usaram os projetos Compose `gr-final-audit-20260922` e `gr-final-report-audit-20260922`, com o override E2E sem portas no host e bancos em `tmpfs`. As dependências foram instaladas pelos locks; o Docker reutilizou camadas/cache disponíveis. Não houve medição de capacidade durante as outras auditorias no mesmo host.

- `docker compose -f compose.yaml -f compose.e2e.yaml -p gr-final-audit-20260922 --profile test build db api frontend frontend-checks e2e`: build aprovado; o candidato com LF foi novamente construído para frontend, checks e E2E.
- `docker compose ... run --rm test`: Ruff, formato de 40 arquivos, mypy de 28 fontes e **158/158 pytest**, sem skip, aprovados. Houve dois avisos de depreciação de Starlette/HTTPX/AnyIO; não foram suprimidos.
- `docker compose ... run --rm upgrade-test`: atualização legada preservou dois usuários, 60 clientes, 240 títulos e totais, com papéis reaplicáveis.
- `docker compose ... run --rm --no-deps frontend-checks`: ESLint, Prettier e TypeScript aprovados no candidato após reproduzir e corrigir a falha Windows.
- `docker compose ... run --rm --no-deps e2e`: **15/15 casos**, um worker, zero retry/skip, em 33,3 s; após corrigir a retenção de HTML, nova carteira descartável aprovou **15/15 em 32,3 s**, com `artifacts/e2e-report/index.html` preservado. Um teste temporário de falha intencional, fora do repositório, retornou 1 e conservou screenshot, contexto, `trace.zip` e HTML após `--rm`. Essa falha esperada valida a coleta; não integra nem substitui a suíte do produto. As imagens pertencem ao candidato local; não substituem as capturas históricas publicadas.
- `python -m unittest discover -s scripts/tests -v`: **16/16**, incluindo códigos reais da CLI para backup válido/corrompido. `python scripts/prove_restore.py plan` e `node --check` dos dois scripts `.cjs` passaram. O pequeno ajuste de indentação em `visual-review.cjs` não altera comportamento.
- Gitleaks **8.30.1**, binário conferido pelo SHA-256 da distribuição: `git --redact --log-opts=--all` examinou 19 commits; `dir --redact` examinou exportação dos arquivos publicáveis, ambos sem achados. A primeira varredura da pasta de execução detectou quatro credenciais descartáveis geradas no `.env` e cinco hashes já documentados; não se confundiu esse diretório privado com conteúdo publicado.
- Trivy **0.74.0**, com o digest do CI, `--scanners vuln --ignorefile /dev/null --exit-code 1`: nenhuma vulnerabilidade relatada nas imagens backend, frontend e database em 22/09/2026. O scanner avisou que Alpine 3.24 não consta da sua lista EOL; resultado não comprova suporte de ciclo de vida nem ausência de falhas desconhecidas.

Os resultados acima são locais, sobre o candidato sem commit. O novo workflow ainda não executou no GitHub. A prova remota e os registros anteriores continuam identificados abaixo com seus próprios SHAs.

**Markdown publicado e candidata local:** em 22/09/2026, o README da raiz foi conferido no GitHub no baseline `4bb9b57e…`, incluindo hierarquia, parágrafos, código, imagens, textos alternativos, legendas, âncoras e navegação. Em 320 px não houve rolagem horizontal global; tabelas, quando presentes nos documentos examinados, mantiveram rolagem na própria região. Essa inspeção pertence à versão publicada, não às edições locais seguintes. O parser GFM também examinou os 13 Markdown da candidata sem falha de caminho local ou âncora.

A candidata foi renderizada em Chromium offline com parser GFM e folhas de estilo obtidas do GitHub. A revisão conjunta dos seis READMEs cobriu 24 combinações: larguras de 1440 e 320 px, temas claro e escuro, quatro por projeto. As imagens carregaram e não houve overflow global; as aberturas e tabelas móveis foram inspecionadas. Esse preview verifica a composição local, mas não reproduz toda a sanitização, navegação ou recursos do GitHub e não comprova publicação da candidata.

A [orientação oficial para README](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes) sustenta a precedência `.github` → raiz → `docs` e a preferência por links relativos internos; a [sintaxe oficial](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#section-links) explica âncoras e títulos repetidos. Um único título principal, a concisão dos parágrafos e a densidade escolhida de imagens são decisões editoriais desta revisão, não cotas impostas pelo GitHub.

A [qualidade do frontend](frontend-quality.md) distingue a revisão estática local das jornadas remotas. O [CI do commit `5718cdad`](https://github.com/arthurjoanes/gestao-recebiveis/actions/runs/35744528178) executou a composição publicada; as provas mais antigas abaixo continuam limitadas às suas próprias versões.

## CI da interface publicada — 22/09/2026

No SHA **`5718cdad3c5052ddbf6f660797121e9c47aa46c8`**, o run **[35744528178](https://github.com/arthurjoanes/gestao-recebiveis/actions/runs/35744528178)**, tentativa 1, terminou com sucesso. Build, 158 testes de backend, atualização do banco, scans e lint/tipos passaram. A suíte Chromium/Playwright 1.63.0 executou **15 casos em 33,4 s: 14 jornadas interativas e 1 caso de formatação BRL**, sem skip, retry ou filtro de seleção; um worker.

O artefato [browser-evidence](https://github.com/arthurjoanes/gestao-recebiveis/actions/runs/35744528178/artifacts/10702621807) contém **21 PNGs e três relatórios de segurança**. Resumo e detalhe longo foram capturados em 1440×900, 1366×768, 768×1024, 390×844 e 320×844; há ainda importação, conflito, baixa, retry, menu e diálogo. A [imagem do Resumo](screenshots/publication-20260922/overview.png) foi copiada sem modificação, com SHA-256 e origem no [recibo](evidence/frontend-ci-20260922.json). Os casos alteram a massa durante a execução, portanto imagens diferentes não constituem uma comparação pareada do mesmo estado. A limpeza do workflow concluiu com sucesso.

O download do artefato [exige login no GitHub e acesso de leitura](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts). A consulta anônima do link retornou 404 nesta auditoria, mas a API do run confirmou o artefato `10702621807`, não expirado, com expiração prevista em **21/12/2026**. O recibo sanitizado e a imagem versionada acima preservam a evidência pública que não depende desse download temporário.

Esta prova remota não altera a recusa local anterior de inicialização. Também não comprova comparação baseline/candidato, zoom nativo, leitor de tela, conformidade AA integral ou desempenho percebido. O SHA acima identifica o código testado; esta atualização documental não foi uma nova execução da aplicação.

## Reproduzir a verificação local

Na raiz do projeto, com Docker Desktop em modo Linux e PowerShell:

```powershell
.\scripts\gestao-recebiveis.ps1 setup
.\scripts\gestao-recebiveis.ps1 test
```

`test` executa Ruff, mypy, pytest com PostgreSQL temporário, ESLint, TypeScript e a jornada Playwright. Os casos de backend verificam importação atômica, valores em centavos, concorrência, pagamentos idempotentes, sessões, permissões e recuperação de lembretes. O navegador cobre importação, repetição, retry, baixa, conflitos, navegação e telas estreitas.

O banco de testes usa `tmpfs`. A jornada tem banco e serviços próprios, no projeto Compose `pf-gestao-recebiveis-e2e`, encerrado pelo script ao terminar. A carteira da demonstração fica em `pf-gestao-recebiveis_postgres-data` e não é usada pelos testes. Capturas e traces ficam em `artifacts/e2e/`; o relatório HTML, em `artifacts/e2e-report/index.html`. Ambos são ignorados pelo Git e preservados no upload do CI, inclusive em falha.

Na revisão de 21/09/2026, uma cópia contendo apenas os arquivos de publicação construiu as imagens e passou os 145 testes de backend, os 12 casos Chromium e as verificações de estilo e tipos. A jornada adicional pelo proxy confirmou 243 títulos após importar três registros, duas tentativas no retry e preservação dos saldos após conflito. A prova de interrupção e reinício manteve uma tentativa e uma entrega, recusando o token do worker antigo. As três imagens de execução tiveram zero achados no Trivy dessa data.

## Revisão autoral de portfólio — 22/09/2026

Revisei README, exemplos, decisões, referências de código e as quatro capturas reais da prova `11adf9df…`. Conservei fontes e imagens históricas: elas mostram a versão que executou a prova, não a composição local posterior. O exemplo CSV de R$ 2.000 e o caso de restore de R$ 125 são fixtures diferentes.

Em uma cópia isolada do estado local, `scripts/check-backend.sh` passou Ruff, formato (40 arquivos), mypy (28 fontes) e **158 testes com PostgreSQL**, em 34,34 s, sem skip. A suíte manteve dois avisos de depreciação Starlette/httpx e AnyIO. Usei banco temporário e fontes atuais montadas somente para leitura; nenhum frontend foi iniciado. O lock Python da imagem era idêntico ao candidato, mas o runtime existente era Python 3.13.12, enquanto o Dockerfile atual fixa 3.13.15: isso verifica fontes/dependências nesse runtime, não uma instalação nova da imagem atual. O ambiente próprio foi encerrado, sem remover volumes alheios.

Para fechar a instalação atual, construí depois somente o backend com o Dockerfile e o lock presentes, em tag própria: **Python 3.13.15**, imagem `sha256:1cf09bded5bb590e9eac61e935553d2f274ffc7b06c14c414cb8b876a09ceae1`. Sem montar fontes sobre a imagem, Ruff, formato, mypy e os **158 testes passaram novamente**, em 89,94 s, com os mesmos dois avisos. A primeira execução foi preservada. Havia outras cargas no host; esses tempos não são comparação de desempenho. O novo banco era temporário e os recursos próprios também foram encerrados. Nenhum frontend foi iniciado.

No host Windows, com Node 24.19.0 e npm 11.17.0, `npm ci --no-audit --fund=false` instalou o frontend do lock em diretório novo; tipos e build de produção passaram. `npm audit --package-lock-only --json` retornou zero achados em 22/09/2026. ESLint passou, mas `npm run lint` saiu com código 1 na etapa Prettier: `responsive-filters.tsx`, `receivable-detail.tsx`, `receivables.tsx` e `tests/journey.spec.ts` já divergiam de formato no snapshot. A correção posterior foi somente Prettier nesses quatro arquivos: conferi que cada saída é exatamente a formatação dos bytes originais, sem edição adicional. O lint completo passou na segunda execução. Tipos e build acima foram executados antes dessa formatação; não a tratam como aprovação visual. Zero achados do npm não cobre imagem, segredo, aplicação ou futuras vulnerabilidades.

Gitleaks 8.30.1 foi executado com redação integral e a configuração existente sobre 165 arquivos rastreados/não ignorados do snapshot e o histórico alcançável (`--all`, 16 commits). O scanner saiu com código 1 nos dois escopos por um alerta `generic-api-key` em `docs/evidence/frontend-quality-static-20260922.json:24`. Conferi que o valor é exatamente o SHA-256 LF de `frontend/src/lib/api.ts`, um digest de evidência, não uma credencial. Naquela execução, não acrescentei exceção nem declarei o scan aprovado. Uma invocação inicial por caminho absoluto também apontou hashes já excepcionados: o scan relativo aplicou os caminhos da configuração existente corretamente e conservou o alerta acima. Trivy 0.74.0 retornou **zero vulnerabilidades** na imagem de backend atual, via Docker local, sem filtro de severidade ou exceções. A base de avisos foi atualizada em 22/09/2026 às 07:24 UTC. O scanner manteve avisos sobre SBOM de terceiros, Alpine 3.24 fora de sua lista de EOL e termos adicionais em metadados de licença. Esse resultado cobre os pacotes de sistema/Python detectados, não o frontend ou uma implantação. Uma tentativa anterior foi interrompida para coordenação do host, sem resultado aproveitado; a execução concluída está registrada no recibo.

**Aditivo de segredos:** depois de recompor novamente o SHA-256 LF, acrescentei uma exceção à regra `generic-api-key`, exigindo em conjunto o caminho exato, a chave JSON `frontend/src/lib/api.ts` e somente aquele digest. As regras padrão e as exceções anteriores permanecem. Com a [configuração restrita](../.gitleaks.toml), o novo scan dos 166 arquivos publicáveis e o histórico completo de 16 commits retornaram zero achados, código 0. Em cópias externas, outro caminho, outra chave e outro valor continuaram detectados; um token fictício no mesmo arquivo também retornou código 1. Os resultados anteriores com código 1 foram preservados. Isso corrige a classificação do digest, sem alterar a aplicação nem validar o frontend.

O [recibo desta revisão](evidence/portfolio-review-20260922.json) identifica versão, instalação, resultados e limites. Conferi os 129 links locais e sete fragmentos de README/docs, além de referências de casos aos testes; não houve renderização Markdown nem nova jornada.

**Situação posterior: design aprovado pelo autor e 15 casos Playwright aprovados no [CI do commit `5718cdad`](https://github.com/arthurjoanes/gestao-recebiveis/actions/runs/35744528178).** A revisão autoral local descrita acima não executou o frontend: respeitou a recusa automática anterior, sem repetir o comando nem usar outro método. O CI remoto posterior executou 14 jornadas interativas e o caso de formatação BRL, com novas capturas. O procedimento local completo `setup`/`test`/`proof` não foi repetido; comparação pareada, zoom nativo, leitor de tela e avaliação completa de acessibilidade continuam fora dessa prova.

## Interface da carteira — 22/09/2026

A composição foi refeita com navegação horizontal, carteira com filtros próximos à lista, resumo que prioriza saldo e títulos vencidos, importação em três passos e detalhe financeiro com identidade e ação juntas. A validação usou frontend compilado em modo standalone e a API da revisão de segurança, em um projeto Compose separado (`ui-gr-redesign-20260922`) com PostgreSQL temporário. As capturas representativas estão em `docs/img/`. As regressões de navegação fazem parte da suíte versionada em `frontend/tests/journey.spec.ts`.

- ESLint, Prettier, TypeScript e build de produção passaram.
- Os 14 testes Playwright passaram no Microsoft Edge/Chromium local. Além dos percursos de importação, baixa, permissões e falhas, há regressões de retorno de lembrete e título: preservação de filtros, página, rolagem e foco; resposta atrasada não rouba o foco de quem está digitando; uma página esvaziada oferece retorno à primeira página.
- As cinco áreas foram verificadas em 1440, 768, 390 e 320 px e com zoom CSS de 200%, sem overflow horizontal da página ou erros JavaScript. A carteira e os vencidos reorganizam as linhas no celular para manter valor e situação visíveis. A fila de lembretes também reorganiza título, estado, horário e acesso às tentativas, sem esconder a ação fora da tela. Tabelas extensas de importação e histórico mantêm rolagem na própria região. A suíte também cobre 1366 px, dados longos, confirmações, navegação por teclado, sessão expirada, erro de rede e ausência de resultados.
- A área de trabalho foi medida até 2560 px: largura limitada a 1500 px e margens centrais. Foram conferidos foco visível, preferência por movimento reduzido e sete pares principais de contraste, todos acima de 4,5:1. Isso não constitui auditoria completa nem certificação WCAG. Zoom CSS também não equivale a zoom nativo do navegador.
- As capturas da carteira, do resumo e do título foram feitas a partir do frontend de produção com dados sintéticos, após jornadas que acrescentam lotes de teste. Seus totais não são uma comparação controlada com capturas anteriores. Houve inspeção dos prints, incluindo valores e nomes longos, além das medidas automáticas.

A mudança reorganiza componentes React, CSS e textos, sem alterar as regras de importação, baixa, autorização ou recuperação. As provas de backend abaixo continuam identificadas pela revisão em que foram realizadas; não representam uma nova prova de carga ou de entrega externa.

## Limpeza de variáveis CSS — 22/09/2026

Foram removidas somente as declarações `--amber` e `--amber-soft`, sem consumidores nos 22 arquivos de `frontend/src` nem no restante das fontes versionadas. A inspeção também conferiu acesso dinâmico a propriedades CSS e a configuração do frontend. O [registro separado](evidence/interface-cleanup-20260922.json) guarda o escopo e os hashes antes/depois. As provas e capturas anteriores foram preservadas; esta limpeza teve apenas conferência de diff e formato, sem novo build, teste de aplicação ou revisão visual.

## Asserção de foco no retorno — 22/09/2026

No [CI do commit `1cf6919`](https://github.com/arthurjoanes/gestao-recebiveis/actions/runs/35694688719), a primeira tentativa parou no download do índice Alpine por erro TLS; a segunda passou build, 158 testes de backend, scans e lint/tipos, mas teve 13 jornadas aprovadas e uma falha. A jornada esperava foco permanente no conteúdo após voltar de um título, embora a aplicação já restaurasse o foco no título depois de carregar a lista. A captura da falha mostrou `TIT-0001` focado, com filtros preservados. Logs e artefatos das duas tentativas foram preservados externamente.

A jornada agora retém somente a resposta de retorno, confere carregamento e foco inicial no conteúdo, libera a resposta e exige o título focado, busca, situação, ambas as datas e uma única linha. Aplicação, timeouts e retries permanecem iguais. Esta conferência local cobre formato, lint e listagem; não inclui a execução do teste corrigido. O resultado de cada execução deve ser conferido no workflow do respectivo commit.

## Correção de segurança — 21/09/2026

A revisão posterior separou as identidades de administração, migração e execução e adicionou admissão persistente ao login. O backend foi reconstruído; os serviços usaram bancos descartáveis em `fix-gr-20260922` e `fix-gr-proof-20260922`, sem publicar portas. Os arquivos locais da execução ficam em `artifacts/security-fix/`, ignorados pelo Git.

- Os 158 testes de backend passaram (13 regressões além dos 145 anteriores), sem skips, assim como Ruff, formatação e mypy. A suíte final verifica o runtime `gestao_app`; somente a limpeza das fixtures/migrações usa `gestao_owner`.
- Os 12 testes Chromium passaram com a API corrigida e a imagem de frontend da revisão anterior, cujo código permaneceu inalterado.
- `upgrade-test` passou: criou o schema anterior `8d2c11`, inseriu 2 usuários, 60 clientes e 240 títulos, e preservou essas contagens e o total pago após a migração. O provisionador foi executado três vezes. O probe também verificou propriedade das sequências e negação de UPDATE em `alembic_version` para o runtime.
- A prova de interrupção/reinício passou novamente com o runtime restrito: uma tentativa, uma entrega e 31 centavos preservados, token antigo recusado, resultado recuperado como `sent`.

Para repetir o teste de atualização isoladamente, depois de construir as imagens:

```sh
docker compose up -d --wait --force-recreate db-upgrade-test
docker compose run --rm --no-deps upgrade-test
docker compose stop db-upgrade-test
```

`db-upgrade-test` contém somente dados sintéticos em `tmpfs`; `--force-recreate` fornece um banco vazio para repetir o probe. Esse comando não é parte do procedimento de atualização de uma carteira real. O script `test` e o CI também executam o probe. O [procedimento de atualização sem remoção de dados](security.md) é separado.

Dois avisos de depreciação do cliente de testes Starlette/httpx e do alias AnyIO permanecem visíveis; não foram suprimidos. Esta correção não repetiu a varredura de dependências nem demonstra proteção de uma implantação pública ou de um provedor de mensagens externo.

## Interrupção e recuperação

```powershell
.\scripts\gestao-recebiveis.ps1 proof
```

O teste de reinício roda em `pf-gestao-recebiveis-proof`, sem portas no host. Interrompe um processo após persistir a aceitação de uma mensagem, reinicia seu PostgreSQL e verifica a reconciliação da mesma tentativa. Também percorre a jornada pela API e pelo navegador. O script remove somente o volume descartável desse projeto.

Comandos, códigos de saída, hashes e resultados ficam em `artifacts/proof/<execução>/`. O código 86 é esperado apenas no ponto de interrupção controlada; qualquer outro resultado inesperado encerra o teste. Isso verifica o provedor fictício persistente; não cobre entrega externa nem perda de disco.

## Restauração em volume novo — 22/09/2026

A [prova de recuperação da carteira](restore-proof.md), execução `11adf9df35ba4314945ffdd4fbaeabfc`, passou em 157,672 s no host local. O destino vazio recebeu as mesmas 16 tabelas públicas e 12 sequências; a baixa de R$ 50 não se repetiu e a tentativa #1 foi reconciliada mantendo a entrega simulada #1. A carteira sintética totalizou R$ 125, com R$ 75 em aberto. Origem e dump ficaram intactos; a limpeza deixou zero recursos dos dois projetos.

O [manifesto](evidence/restore-proof/11adf9df35ba4314945ffdd4fbaeabfc/manifest.json) liga 104 fontes congeladas às imagens, verifica 44 arquivos Python efetivos do backend, registra recusas de corrupção/destino ocupado/modo incorreto e contém quatro capturas reais. O [suplemento posterior](evidence/restore-proof/11adf9df35ba4314945ffdd4fbaeabfc/cli-supplement.json) confirma saídas 0/2 da CLI de integridade, **16 testes host**, Ruff, formato e sintaxe JS. As duas preparações que falharam também estão no [índice](evidence/restore-proof/index.json).

Esta prova não repetiu a suíte completa de 158 testes de backend, as 14 jornadas de interface nem a varredura de dependências. O probe chama a lógica real em etapas, sem worker autônomo; o navegador faz login e leitura dos estados. Provedor externo, perda do host e desempenho com carteira maior continuam sem comprovação. O [plano de integração](provider-integration-plan.md) descreve o que depende desses próximos ambientes.

## Conferência visual adicional

Com o ambiente E2E em execução e a imagem de navegador construída:

```powershell
New-Item -ItemType Directory -Force artifacts/review | Out-Null
docker run --rm --network container:pf-gestao-recebiveis-e2e-frontend-1 `
  --mount "type=bind,source=$((Get-Location).Path)/scripts,target=/review,readonly" `
  --mount "type=bind,source=$((Get-Location).Path)/artifacts/review,target=/evidence" `
  -e SCREENSHOT_DIR=/evidence -e COMPOSE_PROJECT_NAME=pf-gestao-recebiveis-e2e `
  gestao-recebiveis-e2e:local node /review/visual-review.cjs
```

Esse comando adicional exige que o ambiente E2E ainda esteja ativo; `test` o encerra automaticamente. O script confere overflow, posição dos indicadores e tamanho de fonte em cinco larguras, de 320 a 1440 px. As imagens e `reflow.json` são saídas locais, não arquivos para commit.

## Imagens e dependências

O CI usa Trivy 0.74.0, fixado por digest, nas imagens de API, frontend e PostgreSQL. O scanner verifica pacotes do sistema e das aplicações e interrompe a execução se encontrar uma vulnerabilidade, sem arquivo de exceções ou filtro para ignorar casos sem correção. Os relatórios JSON acompanham o artefato do CI.

As bases Python 3.13.15, Node 24.19.0 e PostgreSQL 18.6 usam Alpine 3.24. O frontend instala as correções OpenSSL 3.5.8; API e frontend dispensam gerenciadores de pacotes no estágio de execução. As dependências Python e JavaScript continuam nos arquivos de lock. O banco substitui o `gosu` original por `su-exec`, preservando a troca para o usuário `postgres` antes da inicialização.

Uma varredura limpa vale para as versões e a base de avisos consultadas naquele momento. Não substitui testes, atualização contínua ou uma análise de segurança de uma implantação pública. A base Alpine possui cobertura diferente da Debian, especialmente para problemas ainda sem correção. Os containers de compilação e navegador não fazem parte do ambiente servido ao usuário.

## Banco de versões anteriores

Volumes criados com a antiga imagem Debian não devem ser reutilizados diretamente pela imagem Alpine: as bibliotecas de locale e collation são diferentes. O setup de uma cópia nova usa um volume vazio. Para preservar uma carteira existente, faça uma migração lógica e mantenha o volume original até conferir o resultado:

1. Na versão anterior, pare API e worker. Faça um `pg_dump --format=custom` da base `gestao_recebiveis` e guarde uma cópia fora do container. Em PowerShell, use um arquivo dentro do container seguido de `docker compose cp`; não redirecione o dump binário pelo pipeline.
2. Em uma cópia separada da versão atual, configure `.env` e construa `db`, `api` e `frontend`. Use outro nome de projeto Compose, por exemplo `docker compose -p recebiveis-migracao`, em todos os comandos desta cópia. Isso cria outro volume. Mantenha a aplicação anterior parada para liberar as portas.
3. Inicie apenas `db`, copie o dump para esse container e restaure com `pg_restore --no-owner --no-privileges -U gestao_recebiveis -d gestao_recebiveis`. Rode `migrate`; não rode `seed` sobre uma carteira restaurada.
4. Inicie API, worker e frontend nesse mesmo projeto. Confira contagens de clientes, títulos, pagamentos, entregas e saldos contra o banco anterior antes de adotar a nova cópia. Os scripts PowerShell têm nome de projeto fixo; nessa migração use os comandos Compose com `-p recebiveis-migracao`.

Esses passos preservam o volume anterior e permitem retornar à versão que o criou. A prova de reinício valida persistência na base atual; não é uma prova de migração de uma carteira externa.

## Conferência dos arquivos de publicação — 22/09/2026

Gitleaks 8.30.1 identificou quatro ocorrências dos hashes SHA-256 de `auth.py` e `test_api.py` dentro dos comandos registrados em dois manifestos da restauração. Os valores foram recalculados a partir das fontes. A [configuração](../.gitleaks.toml) conserva as regras padrão e limita a exceção à regra, aos dois valores e aos dois caminhos exatos. O [controle separado](evidence/restore-proof/secret-fingerprint-review.json) confirmou ausência de achados nos arquivos publicáveis e detecção de uma chave sintética no mesmo arquivo permitido. A verificação de histórico completo é feita pelo workflow de segredos de cada commit; caches, `.env` local e artefatos ignorados não são parte da publicação.

## Ajuste posterior à prova

O [CI de `7607f9a`](https://github.com/arthurjoanes/gestao-recebiveis/actions/runs/35698694847) construiu as imagens, mas parou em cinco erros de ordem de importações no novo probe. A checagem local anterior partira da raiz, enquanto o CI executa Ruff em `backend`; a classificação dos imports diferiu. Foram reorganizados somente esses blocos. O [registro do ajuste](evidence/restore-proof/post-publication-import-order.json) confere hashes e estrutura do código, descontando apenas a ordem dos imports, e registra lint/formato no diretório do CI e os 16 testes host aprovados. A execução financeira não foi repetida; seu manifesto e fontes originais permanecem preservados. O resultado do novo CI pertence ao novo commit, não ao que falhou.
