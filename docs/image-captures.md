# Capturas da interface

## Apresentação

A [imagem do Resumo](readme/overview.png), usada no README, foi capturada na aplicação local em 12/10/2026, no Edge 155.0.4283.45, com viewport 1440×900 CSS px. A aplicação estava compilada em produção e autenticada como operador. O PNG conserva a página inteira, sem edição de pixels.

A carteira é fictícia: seed de 240 títulos mais três títulos de teste, 61 clientes, 49 recebimentos e cinco lotes. A data comercial é 17/08/2026. O Resumo mostra R$ 516.653,77 em aberto, em 195 títulos, e R$ 118.316,93 recebidos, em 49 recebimentos. Esses valores descrevem o estado da demonstração capturada.

A [imagem do CI de 22/09/2026](screenshots/publication-20260922/overview.png) pertence ao commit `5718cdad`; o [recibo](evidence/frontend-ci-20260922.json) registra sua origem e hash. Ela não representa o estado atual da carteira.

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

O [coletor](../scripts/capture_docs.cjs) exige pasta vazia para não sobrescrever capturas. Os valores dependem da carteira local; uma instalação com seed padrão não terá necessariamente os mesmos totais da imagem de apresentação. Inspecione o resultado antes de incluí-lo na documentação. Saídas temporárias ficam em `artifacts/`, ignorado pelo Git.

## Provas de restauração

Os quatro PNGs de `screenshots/restore-proof/11adf9df35ba4314945ffdd4fbaeabfc/` integram a [prova de restauração de 22/09/2026](restore-proof.md). O [manifesto](evidence/restore-proof/11adf9df35ba4314945ffdd4fbaeabfc/manifest.json) conserva cenário e resultados.

## Evolução de 12/10/2026

As cinco capturas de `screenshots/restore-proof/6e75361b018645ffa98bce7ad338d4d4/` vieram do navegador durante a [restauração final](restore-proof.md#cenário-de-parcelas--candidato-de-12102026). Mostram lembrete, título integral, título parcial, extrato e aging. A viewport é 1440×1080; os PNGs conservam a página inteira. O [manifesto](evidence/restore-proof/6e75361b018645ffa98bce7ad338d4d4/manifest.json) registra fontes, imagens, hashes e resultados.

O [coletor](../scripts/capture_restore_story.cjs) consulta após login e espera totais e linhas prontos. O extrato mostra original R$ 125, recebido R$ 75 e saldo R$ 50; o aging inclui apenas o saldo residual do título parcial. A execução anterior `1054efee…` passou financeiramente, mas capturou extrato e aging durante carregamento; suas imagens não representam relatórios prontos.

Capturas não substituem testes de cálculo, identidade ou persistência, nem verificam leitor de tela ou conformidade de acessibilidade integral. Preserve imagens e manifestos de uma prova concluída; novas execuções recebem destinos próprios.

## Leitura visual conferida em 13/10/2026

O Resumo mostra a página completa e distingue saldo aberto de recebimentos. Seus R$ 244.250,17 vencidos e R$ 272.403,60 em dia somam R$ 516.653,77; os R$ 118.316,93 recebidos pertencem a outro recorte. A imagem apresenta indicadores e uma tabela, sem gráfico de série temporal.

Na execução `6e75361b…`, o extrato mostra os dois títulos, os dois recebimentos e a conta R$ 125 − R$ 75 = R$ 50. O aging mostra apenas esse saldo residual na faixa em dia. São páginas completas e legíveis quando abertas; a captura de aging conserva o texto antigo “1 títulos”, anterior à correção de singular/plural. As imagens `06` e `07` de `1054efee…` mostram “Carregando…”, por isso não servem para apresentar o extrato ou o aging concluídos. Permanecem como registro da captura incompleta, já substituída na apresentação pela execução final.
