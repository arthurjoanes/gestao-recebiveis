# Verificação local

O [candidato de qualidade do frontend](frontend-quality.md) tem uma matriz própria e distingue as verificações estáticas das jornadas bloqueadas. As capturas e execuções históricas abaixo não validam automaticamente esse candidato.

Na raiz do projeto, com Docker Desktop em modo Linux e PowerShell:

```powershell
.\scripts\gestao-recebiveis.ps1 setup
.\scripts\gestao-recebiveis.ps1 test
```

`test` executa Ruff, mypy, pytest com PostgreSQL temporário, ESLint, TypeScript e a jornada Playwright. Os casos de backend verificam importação atômica, valores em centavos, concorrência, pagamentos idempotentes, sessões, permissões e recuperação de lembretes. O navegador cobre importação, repetição, retry, baixa, conflitos, navegação e telas estreitas.

O banco de testes usa `tmpfs`. A jornada tem banco e serviços próprios, no projeto Compose `pf-gestao-recebiveis-e2e`, encerrado pelo script ao terminar. A carteira da demonstração fica em `pf-gestao-recebiveis_postgres-data` e não é usada pelos testes. Os resultados do navegador ficam em `artifacts/e2e/`, ignorado pelo Git.

Na revisão de 21/09/2026, uma cópia contendo apenas os arquivos de publicação construiu as imagens e passou os 145 testes de backend, os 12 casos Chromium e as verificações de estilo e tipos. A jornada adicional pelo proxy confirmou 243 títulos após importar três registros, duas tentativas no retry e preservação dos saldos após conflito. A prova de interrupção e reinício manteve uma tentativa e uma entrega, recusando o token do worker antigo. As três imagens de execução tiveram zero achados no Trivy dessa data.

## Revisão autoral de portfólio — 22/09/2026

Revisei README, exemplos, decisões, referências de código e as quatro capturas reais da prova `11adf9df…`. Conservei fontes e imagens históricas: elas mostram a versão que executou a prova, não a composição local posterior. O exemplo CSV de R$ 2.000 e o caso de restore de R$ 125 são fixtures diferentes.

Em uma cópia isolada do estado local, `scripts/check-backend.sh` passou Ruff, formato (40 arquivos), mypy (28 fontes) e **158 testes com PostgreSQL**, em 34,34 s, sem skip. A suíte manteve dois avisos de depreciação Starlette/httpx e AnyIO. Usei banco temporário e fontes atuais montadas somente para leitura; nenhum frontend foi iniciado. O lock Python da imagem era idêntico ao candidato, mas o runtime existente era Python 3.13.12, enquanto o Dockerfile atual fixa 3.13.15: isso verifica fontes/dependências nesse runtime, não uma instalação nova da imagem atual. O ambiente próprio foi encerrado, sem remover volumes alheios.

Para fechar a instalação atual, construí depois somente o backend com o Dockerfile e o lock presentes, em tag própria: **Python 3.13.15**, imagem `sha256:1cf09bded5bb590e9eac61e935553d2f274ffc7b06c14c414cb8b876a09ceae1`. Sem montar fontes sobre a imagem, Ruff, formato, mypy e os **158 testes passaram novamente**, em 89,94 s, com os mesmos dois avisos. A primeira execução foi preservada. Havia outras cargas no host; esses tempos não são comparação de desempenho. O novo banco era temporário e os recursos próprios também foram encerrados. Nenhum frontend foi iniciado.

No host Windows, com Node 24.19.0 e npm 11.17.0, `npm ci --no-audit --fund=false` instalou o frontend do lock em diretório novo; tipos e build de produção passaram. `npm audit --package-lock-only --json` retornou zero achados em 22/09/2026. ESLint passou, mas `npm run lint` saiu com código 1 na etapa Prettier: `responsive-filters.tsx`, `receivable-detail.tsx`, `receivables.tsx` e `tests/journey.spec.ts` já divergiam de formato no snapshot. A correção posterior foi somente Prettier nesses quatro arquivos: conferi que cada saída é exatamente a formatação dos bytes originais, sem edição adicional. O lint completo passou na segunda execução. Tipos e build acima foram executados antes dessa formatação; não a tratam como aprovação visual. Zero achados do npm não cobre imagem, segredo, aplicação ou futuras vulnerabilidades.

Gitleaks 8.30.1 foi executado com redação integral e a configuração existente sobre 165 arquivos rastreados/não ignorados do snapshot e o histórico alcançável (`--all`, 16 commits). O scanner saiu com código 1 nos dois escopos por um alerta `generic-api-key` em `docs/evidence/frontend-quality-static-20260922.json:24`. Conferi que o valor é exatamente o SHA-256 LF de `frontend/src/lib/api.ts`, um digest de evidência, não uma credencial. Naquela execução, não acrescentei exceção nem declarei o scan aprovado. Uma invocação inicial por caminho absoluto também apontou hashes já excepcionados: o scan relativo aplicou os caminhos da configuração existente corretamente e conservou o alerta acima. Trivy 0.74.0 retornou **zero vulnerabilidades** na imagem de backend atual, via Docker local, sem filtro de severidade ou exceções. A base de avisos foi atualizada em 22/09/2026 às 07:24 UTC. O scanner manteve avisos sobre SBOM de terceiros, Alpine 3.24 fora de sua lista de EOL e termos adicionais em metadados de licença. Esse resultado cobre os pacotes de sistema/Python detectados, não o frontend ou uma implantação. Uma tentativa anterior foi interrompida para coordenação do host, sem resultado aproveitado; a execução concluída está registrada no recibo.

**Aditivo de segredos:** depois de recompor novamente o SHA-256 LF, acrescentei uma exceção à regra `generic-api-key`, exigindo em conjunto o caminho exato, a chave JSON `frontend/src/lib/api.ts` e somente aquele digest. As regras padrão e as exceções anteriores permanecem. Com a [configuração restrita](../.gitleaks.toml), o novo scan dos 166 arquivos publicáveis e o histórico completo de 16 commits retornaram zero achados, código 0. Em cópias externas, outro caminho, outra chave e outro valor continuaram detectados; um token fictício no mesmo arquivo também retornou código 1. Os resultados anteriores com código 1 foram preservados. Isso corrige a classificação do digest, sem alterar a aplicação nem validar o frontend.

O [recibo desta revisão](evidence/portfolio-review-20260922.json) identifica versão, instalação, resultados e limites. Conferi os 129 links locais e sete fragmentos de README/docs, além de referências de casos aos testes; não houve renderização Markdown nem nova jornada.

**Situação: design aprovado pelo autor em 22/09/2026; validação de execução da interface atual pendente.** O lançamento Next permanece bloqueado pela revisão automática anterior; não repeti o comando nem usei outra forma de iniciar o frontend. Não há novas jornadas, capturas ou avaliação com leitor de tela; a aprovação do design não é prova de execução da interface. O procedimento completo `setup`/`test`/`proof` inclui frontend e não foi repetido. Os testes atuais de backend não transferem aprovação para a interface local.

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
