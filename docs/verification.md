# Verificação local

Na raiz do projeto, com Docker Desktop em modo Linux e PowerShell:

```powershell
.\scripts\gestao-recebiveis.ps1 setup
.\scripts\gestao-recebiveis.ps1 test
```

`test` executa Ruff, mypy, pytest com PostgreSQL temporário, ESLint, TypeScript e a jornada Playwright. Os casos de backend verificam importação atômica, valores em centavos, concorrência, pagamentos idempotentes, sessões, permissões e recuperação de lembretes. O navegador cobre importação, repetição, retry, baixa, conflitos, navegação e telas estreitas.

O banco de testes usa `tmpfs`. A jornada tem banco e serviços próprios, no projeto Compose `pf-gestao-recebiveis-e2e`, encerrado pelo script ao terminar. A carteira da demonstração fica em `pf-gestao-recebiveis_postgres-data` e não é usada pelos testes. Os resultados do navegador ficam em `artifacts/e2e/`, ignorado pelo Git.

Na revisão de 21/09/2026, uma cópia contendo apenas os arquivos de publicação construiu as imagens e passou os 145 testes de backend, os 12 casos Chromium e as verificações de estilo e tipos. A jornada adicional pelo proxy confirmou 243 títulos após importar três registros, duas tentativas no retry e preservação dos saldos após conflito. A prova de interrupção e reinício manteve uma tentativa e uma entrega, recusando o token do worker antigo. As três imagens de execução tiveram zero achados no Trivy dessa data.

## Interrupção e recuperação

```powershell
.\scripts\gestao-recebiveis.ps1 proof
```

O teste de reinício roda em `pf-gestao-recebiveis-proof`, sem portas no host. Interrompe um processo após persistir a aceitação de uma mensagem, reinicia seu PostgreSQL e verifica a reconciliação da mesma tentativa. Também percorre a jornada pela API e pelo navegador. O script remove somente o volume descartável desse projeto.

Comandos, códigos de saída, hashes e resultados ficam em `artifacts/proof/<execução>/`. O código 86 é esperado apenas no ponto de interrupção controlada; qualquer outro resultado inesperado encerra o teste. Isso verifica o provedor fictício persistente; não cobre entrega externa nem perda de disco.

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
