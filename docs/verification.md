# Verificação local

Os resultados pertencem às versões e aos ambientes indicados em cada execução. Alterações na documentação não reexecutam as suítes. Testes de cálculo, identidade, concorrência e recuperação complementam os percursos HTTP e de navegador.

## Builds e testes locais — 22/09/2026

Base examinada: [`4bb9b57`](https://github.com/arthurjoanes/gestao-recebiveis/tree/4bb9b57edc1b298cada00bdf9045efb861ed0faa), com as alterações candidatas descritas abaixo.

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

## CI da interface publicada — 22/09/2026

No SHA **`5718cdad3c5052ddbf6f660797121e9c47aa46c8`**, o run **[35744528178](https://github.com/arthurjoanes/gestao-recebiveis/actions/runs/35744528178)**, tentativa 1, terminou com sucesso. Build, 158 testes de backend, atualização do banco, scans e lint/tipos passaram. A suíte Chromium/Playwright 1.63.0 executou **15 casos em 33,4 s: 14 jornadas interativas e 1 caso de formatação BRL**, sem skip, retry ou filtro de seleção; um worker.

O artefato [browser-evidence](https://github.com/arthurjoanes/gestao-recebiveis/actions/runs/35744528178/artifacts/10702621807) contém **21 PNGs e três relatórios de segurança**. Resumo e detalhe longo foram capturados em 1440×900, 1366×768, 768×1024, 390×844 e 320×844; há ainda importação, conflito, baixa, retry, menu e diálogo. A [imagem do Resumo](screenshots/publication-20260922/overview.png) foi copiada sem modificação, com SHA-256 e origem no [recibo](evidence/frontend-ci-20260922.json). Os casos alteram a massa durante a execução, portanto imagens diferentes não constituem uma comparação pareada do mesmo estado. A limpeza do workflow concluiu com sucesso.

O download do artefato [exige login no GitHub e acesso de leitura](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts). A consulta anônima do link retornou 404 nesta auditoria, mas a API do run confirmou o artefato `10702621807`, não expirado, com expiração prevista em **21/12/2026**. O recibo sanitizado e a imagem versionada acima preservam a evidência pública que não depende desse download temporário.

Esta prova remota não verifica zoom nativo, leitor de tela, conformidade WCAG integral ou desempenho de produção. O SHA acima identifica o código testado.

## Reproduzir a verificação local

Na raiz do projeto, com Docker Desktop em modo Linux e PowerShell:

```powershell
.\scripts\gestao-recebiveis.ps1 setup
.\scripts\gestao-recebiveis.ps1 test
```

`test` executa Ruff, mypy, pytest com PostgreSQL temporário, ESLint, TypeScript e a jornada Playwright. Os casos de backend verificam importação atômica, valores em centavos, concorrência, pagamentos idempotentes, sessões, permissões e recuperação de lembretes. O navegador cobre importação, repetição, retry, baixa, conflitos, navegação e telas estreitas.

O banco de testes usa `tmpfs`. A jornada tem banco e serviços próprios, no projeto Compose `pf-gestao-recebiveis-e2e`, encerrado pelo script ao terminar. A carteira da demonstração fica em `pf-gestao-recebiveis_postgres-data` e não é usada pelos testes. Capturas e traces ficam em `artifacts/e2e/`; o relatório HTML, em `artifacts/e2e-report/index.html`. Ambos são ignorados pelo Git e preservados no upload do CI, inclusive em falha.

Na revisão de 21/09/2026, uma cópia contendo apenas os arquivos de publicação construiu as imagens e passou os 145 testes de backend, os 12 casos Chromium e as verificações de estilo e tipos. A jornada adicional pelo proxy confirmou 243 títulos após importar três registros, duas tentativas no retry e preservação dos saldos após conflito. A prova de interrupção e reinício manteve uma tentativa e uma entrega, recusando o token do worker antigo. As três imagens de execução tiveram zero achados no Trivy dessa data.

## Backend e dependências — 22/09/2026

O [recibo local](evidence/portfolio-review-20260922.json) identifica fontes, instalação e resultados. O backend construído com Python 3.13.15 aprovou Ruff, formato, mypy e **158 testes com PostgreSQL** em 89,94 s, com dois avisos de depreciação. Uma execução anterior com as mesmas fontes e locks em Python 3.13.12 também passou, mas não validava a imagem nova. Esses tempos não são comparação de desempenho.

No Windows, Node 24.19.0 e npm 11.17.0 instalaram o frontend pelo lock; tipos e build passaram. O lint completo passou após formatação Prettier de quatro arquivos. O audit do lock retornou zero achados naquela data. Trivy 0.74.0 não encontrou vulnerabilidades na imagem de backend; o resultado não abrangia frontend ou implantação pública.

A varredura inicial de segredos classificou um SHA-256 de fonte como `generic-api-key`. O digest foi recalculado e recebeu uma exceção que exige caminho, chave JSON e valor exatos. Com a [configuração restrita](../.gitleaks.toml), os 166 arquivos publicáveis e o histórico de 16 commits retornaram zero achados. Controles em outro caminho, chave ou valor, e um token fictício no mesmo arquivo, continuaram detectados. O recibo conserva os resultados anteriores.

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

## Código e evidências relacionados

[workflow](../.github/workflows/ci.yml).

## Pagamentos parciais, aging e extrato (12/10/2026)

A execução `ec3bf363168b` validou o candidato sobre `6dcc674`, com alterações ainda não commitadas. O [manifesto](evidence/evolution-20261012/ec3bf363168b/manifest.json) registra o SHA-256 do diff, os hashes das 127 fontes copiadas para runtime privado, as imagens e os comandos realmente executados. Todas essas fontes permaneceram iguais até o encerramento dos testes; alterações posteriores na documentação não ampliam essa prova.

| Conferência | Resultado local |
| --- | --- |
| Builds sequenciais `db`, `api`, `frontend`, `frontend-checks`, `e2e` | Cinco aprovados; frontend compilado em produção com Next.js 16.3.8 |
| `run --rm test`, Python 3.13.15 | Ruff, formato, mypy, Alembic e **218 testes aprovados**, sem skips; dois avisos de depreciação visíveis |
| Banco anterior → migração atual | **48 recebimentos legados** preservados e repetidos, incluindo IDs, timestamps e hashes; inconsistência, pagamento zero e downgrade destrutivo recusados; papéis provisionados três vezes |
| `frontend-checks` | ESLint, Prettier, geração de tipos Next e TypeScript aprovados |
| Chromium/Playwright 1.63.0 | **22 casos aprovados** em 41,8 s, um worker, zero retries e skips |
| Guardas host e CLI de backup, Python 3.13 | **22 testes aprovados**; `prove_restore.py plan --allow-other-projects` retornou 0 |
| Trivy 0.74.0, digest do CI | API, frontend e PostgreSQL: saída 0 e zero vulnerabilidades, todas as severidades, sem ignorefile de exceções |
| `npm audit --omit=dev --json` na imagem de checks | Saída 0, zero vulnerabilidades de runtime |

Os testes novos cobrem centavos e bigint, corridas de pagamento/cancelamento, hash legado e intenção explícita, reimportação após parcela, fronteiras do aging, filtros independentes e pagamento sincronizado entre consultas de um snapshot. As jornadas verificam resposta perdida após commit, rejeição definitiva após lookup, expiração local com diálogo aberto, isolamento/limpeza por conta, reader, retorno com filtros/páginas e impressão do extrato. A paginação impressa identifica o recorte exibido; seus totais abrangem todo o recorte consultado.

Cada projeto Compose recebeu namespace, tags de imagens e credenciais descartáveis próprios, fora do Git. O E2E usou `compose.e2e.yaml`, sem portas do host e com banco em tmpfs. A limpeza inspecionou labels e removeu somente os projetos dessa execução. Logs publicáveis estão ligados por hash no manifesto; configurações, credenciais, traces de sessão e relatórios brutos permanecem no runtime privado.

As tentativas anteriores continuam registradas. `45f004bb7360` passou backend e migração, mas teve 18/21 casos de navegador: overflow do menu em 768 px e dois seletores de teste foram corrigidos. Um erro de codificação do console do executor ocorreu depois de um build bem-sucedido; os builds restantes foram retomados. `e6a86186008a` passou 21/21 casos e revelou os advisories de zlib e Mako no Trivy. A execução final acima incorporou essas correções e o 22º caso, sem silenciar falhas. A primeira tentativa de restore, [091dc9f…](evidence/restore-proof/091dc9f332cf47b8a447f5869584337b/manifest.json), falhou com Docker indisponível antes de criar recursos.

Não foram acrescentadas bibliotecas. Atualizações pontuais resolveram avisos encontrados: [sharp 0.35.5](https://github.com/advisories/GHSA-wq5f-xc86-pv6w), [source-map-js 1.2.2](https://github.com/advisories/GHSA-68fv-2mgg-jv7q), [Mako 1.4.2](https://github.com/sqlalchemy/mako/security/advisories/GHSA-5639-2j2p-m4mx) e [zlib 1.3.2-r1 no Alpine 3.24](https://secdb.alpinelinux.org/v3.24/main.json). Bases, digests, versões diretas e gates do CI foram preservados. O audit completo ainda informa **cinco achados high na cadeia de desenvolvimento de braces**, cujo [advisory não tem versão corrigida](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm); não foi aplicado o downgrade sugerido por `audit fix --force`. O Trivy também emitiu avisos de precisão de SBOM de terceiros e de metadados EOL do Alpine, preservados nos logs.

A prova usa dados sintéticos, posição atual e FakeProvider. Não demonstra ledger histórico, snapshot entre páginas, conciliação bancária, envio externo, perda do host ou desempenho de produção. A revisão visual universal, leitor de tela e zoom nativo continuam pendentes; as verificações funcionais e de reflow não constituem certificação WCAG.

A [restauração final `6e75361b…`](evidence/restore-proof/6e75361b018645ffa98bce7ad338d4d4/manifest.json) passou em **197,941 s**, em host compartilhado com 23 containers externos observados no início. O destino recebeu as mesmas 16 tabelas públicas e 12 sequências; os recebimentos de R$ 50 integral e R$ 25 parcial conservaram IDs e conteúdo. Repetir ambas as chaves não alterou o estado. A reconciliação conservou tentativa, payload autorizado de R$ 50 e a única entrega simulada. Corrupção, destino ocupado e modo incorreto foram recusados; origem e dump permaneceram intactos. A limpeza deixou zero recursos nos dois projetos próprios.

As cinco [capturas da execução final](image-captures.md#evolução-de-12102026) mostram somente telas funcionais alteradas. Após a suíte principal, o único ajuste em fontes de execução foi no coletor: a primeira [restauração `1054efee…`](evidence/restore-proof/1054efee71e84949a4951d5f752c5be2/manifest.json) passou financeiramente em 192,785 s, mas capturou extrato e aging durante carregamento. O coletor agora espera totais e linhas visíveis e valida os relatórios pela API; sua sintaxe passou em `node --check`. A prova final congelou essa nova versão e passou novamente, com captura pronta e inspeção visual. Aplicação, migração, dependências e testes permaneceram iguais aos da suíte de 218/22 casos.

A conferência adicional de Ruff nos dois scripts Python, sem indicar configuração, encontrou seis apontamentos e diferenças de formatação sob regras fora do gate versionado. Com `--config backend/pyproject.toml`, lint e formato passaram nos dois arquivos, sem alteração de código para essa conferência.

Gitleaks 8.30.1 verificou os arquivos publicáveis com as regras padrão e a configuração do repositório. Os achados novos eram os SHA-256 de `auth.py` e `test_api.py` nos comandos de verificação de fontes dos dois manifestos de outubro. Os valores foram recalculados e conferidos contra as cópias congeladas. A exceção mantém `AND` entre caminhos exatos e fingerprints exatos; um controle com chave sintética no mesmo manifesto continuou sendo detectado. O [registro dos fingerprints](evidence/evolution-20261012/ec3bf363168b/secret-fingerprint-review.json) contém versões, hashes e resultados redigidos. A [varredura final de 254 arquivos](evidence/evolution-20261012/ec3bf363168b/secret-final-scan.json), incluindo os 21 logs públicos sanitizados, retornou zero achados. Esses logs conservam espaços e linhas produzidos pelos comandos; a conferência de whitespace do diff de fontes/documentação os exclui. O workflow de histórico completo permanece habilitado.

## Sessão, confirmação e reflow — 12/10/2026

A validação local das alterações incluídas em `075841b` cobriu a prévia de parcela/quitação, recuperação após timeout, respostas de outra sessão, revogação de acesso, filtros de datas e valores completos em telas menores. As fontes de aplicação testadas permaneceram iguais até o commit; a documentação foi atualizada separadamente.

| Verificação | Resultado |
| --- | --- |
| Build de produção | Next.js, saída 0 |
| ESLint, Prettier e TypeScript | Saída 0 |
| Backend | 218 testes em 77,48 s; dois avisos de depreciação |
| Migração | 48 recebimentos legados preservados e repetidos, saída 0 |
| Playwright | 37/37 casos em cerca de 1,7 min, um worker, zero skip/retry |
| Navegadores | Chromium 153.0.8010.12; Firefox 155.0 no percurso leitor → aging → título → extrato |
| Trivy 0.74.0 | Três imagens de runtime, zero vulnerabilidades, sem filtro de severidade ou exceções |
| Axe-core 4.13.0 | 46 estados, zero violações; três resultados inconclusivos de contraste examinados manualmente |

Backend, migrações, banco, dados e seus locks não mudaram após os respectivos testes. Backend e migração foram reaproveitados por igualdade de fontes; não foram executados novamente no ambiente final de navegador. Build e capturas usaram as mesmas imagens de runtime por ID imutável; a última mudança foi no teste que reabre o filtro móvel após seu recolhimento automático. As provas de restauração mantêm suas datas e hashes.

Os testes exercitaram 320, 390, 768, 1024 e 1440 CSS px, teclado, retorno de foco, texto ampliado por CSS e movimento reduzido. Os resultados inconclusivos de `.payment-preview > p` em 768, 1024 e 1440 px foram conferidos: texto e fundo tinham contraste de 12,736:1, sem sobreposição com título ou valores. Zoom nativo, leitor de tela e desempenho de produção não foram verificados; esse escopo não certifica conformidade WCAG integral.
