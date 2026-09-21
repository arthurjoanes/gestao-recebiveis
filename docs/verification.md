# Verificação local

Na raiz do projeto, com Docker Desktop em modo Linux e PowerShell:

```powershell
.\scripts\gestao-recebiveis.ps1 setup
.\scripts\gestao-recebiveis.ps1 test
```

`test` executa Ruff, mypy, pytest com PostgreSQL temporário, ESLint, TypeScript e a jornada Playwright. Os casos de backend verificam importação atômica, valores em centavos, concorrência, pagamentos idempotentes, sessões, permissões e recuperação de lembretes. O navegador cobre importação, repetição, retry, baixa, conflitos, navegação e telas estreitas.

O banco de testes usa `tmpfs`. A jornada tem banco e serviços próprios, no projeto Compose `pf-gestao-recebiveis-e2e`, encerrado pelo script ao terminar. A carteira da demonstração fica em `pf-gestao-recebiveis_postgres-data` e não é usada pelos testes. Os resultados do navegador ficam em `artifacts/e2e/`, ignorado pelo Git.

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
