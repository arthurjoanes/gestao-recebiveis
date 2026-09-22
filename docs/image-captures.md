# Capturas da interface

As seis capturas de `screenshots/current-20260922/` vieram do Chromium/Playwright 1.63.0 acessando a aplicação local em 22/09/2026. A fonte autenticada corresponde a `deade1369`; o [registro da captura](screenshots/current-20260922/capture.json) contém horário, viewports e SHA-256. São recortes nativos de componentes, sem edição de pixels: viewport desktop 1440×1000 ou móvel 390×844. O coletor registra o seletor e as dimensões de cada foco; os recortes móveis têm no máximo 650 px de altura. Nenhuma captura de página inteira é incorporada nas docs.

| Tela atual                                                          | O que conferir                                                            |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| [Resumo](screenshots/current-20260922/resumo.png)                   | Aberto de R$ 515.153,87, vencido e em dia como partes; recebido separado  |
| [Carteira](screenshots/current-20260922/carteira.png)               | 240 títulos fictícios, filtros e paginação                                |
| [Título](screenshots/current-20260922/titulo.png)                   | Saldo de TIT-0001, R$ 1.217,39, situação, ações e dados do título         |
| [Importações](screenshots/current-20260922/importacoes.png)         | Área de escolha do CSV e regras de formato; nada foi importado na captura |
| [Lembretes](screenshots/current-20260922/lembretes.png)             | Fila simulada e acesso a tentativas; processamento não alterado           |
| [Resumo no celular](screenshots/current-20260922/resumo-mobile.png) | Somente posição em aberto, vencido e em dia, em 358×610 px                |

As telas foram inspecionadas visualmente. A automação conferiu login, títulos esperados, conteúdo carregado, ausência de erros JavaScript e overflow nas seis vistas. Não efetuou pagamentos, cancelamentos, importações, reset nem envio externo. Não substitui a suíte funcional, comparação pixel a pixel com baseline, leitor de tela ou auditoria de acessibilidade integral.

## Reproduzir

Com o setup iniciado, na raiz, PowerShell 7:

```powershell
docker compose --profile test build e2e
$captureOutput = Join-Path $PWD 'artifacts/docs-capture-nova'
New-Item -ItemType Directory -Path $captureOutput
docker run --rm --network container:pf-gestao-recebiveis-frontend-1 `
  --mount "type=bind,source=$PWD,target=/repo,readonly" `
  --mount "type=bind,source=$captureOutput,target=/capture" `
  --env NODE_PATH=/app/node_modules --env DOCS_SCREENSHOT_DIR=/capture `
  --env "SOURCE_COMMIT=$(git rev-parse HEAD)" `
  --entrypoint node gestao-recebiveis-e2e:local /repo/scripts/capture_docs.cjs
```

O [coletor](../scripts/capture_docs.cjs) exige pasta vazia para não sobrescrever provas. A carteira local determina valores, datas de eventos e lembretes; esta execução usou o seed padrão com referência comercial 17/08/2026. Inspecione o resultado antes de promovê-lo a documentação.

## Arquivo histórico e propostas

- Os três PNGs de `img/` mostram o layout anterior verde. Seus hashes constam em [interface-cleanup-20260922.json](evidence/interface-cleanup-20260922.json); não são imagens de apresentação atual.
- Os quatro PNGs de `screenshots/restore-proof/11adf9df35ba4314945ffdd4fbaeabfc/` integram a [prova histórica de restauração](restore-proof.md). Não foram recapturados nem adulterados; as provas completas ficam em links, sem imagens longas incorporadas.
- [overview.png do CI](screenshots/publication-20260922/overview.png) conserva o [recibo histórico](evidence/frontend-ci-20260922.json). A composição é a mesma direção visual, mas o estado da massa pertence àquela execução.
- Os quatro PNGs em `design/` são propostas e espécimes, não telas reais. A [decisão de design](frontend-quality.md) identifica seu uso.

A revisão inventariou os 12 PNGs anteriores, suas referências e hashes, sem duplicatas binárias internas. Todos têm função documental; nenhuma imagem de prova foi excluída. A fixture `repeated.csv` repete `valid.csv` deliberadamente para testar idempotência; não é resíduo.
