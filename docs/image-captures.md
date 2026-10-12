# Capturas da interface

A [revisão de UI/UX de 12/10/2026](uiux-20261012.md) tem pasta própria em `screenshots/uiux-20261012/`, com 46 imagens em `before/` e 46 em `after/`. O [registro agregado](evidence/uiux-20261012/review.json) identifica fixture, fontes, dimensões, hashes das imagens e verificações. As seções históricas conservam o contexto das execuções anteriores.

As seis capturas de `screenshots/current-20260922/` vieram do Chromium/Playwright 1.63.0 acessando a aplicação local em 22/09/2026. A fonte autenticada corresponde a `deade1369`; o [registro da captura](screenshots/current-20260922/capture.json) contém horário, viewports e SHA-256. São recortes nativos de componentes, sem edição de pixels: viewport desktop 1440×1000 ou móvel 390×844. O coletor registra o seletor e as dimensões de cada foco; os recortes móveis têm no máximo 650 px de altura. Essas seis imagens não são capturas de página inteira.

| Tela de 22/09/2026                                                   | O que conferir                                                            |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| [Resumo](screenshots/current-20260922/resumo.png)                   | Aberto de R$ 515.153,87, vencido e em dia como partes; recebido separado  |
| [Carteira](screenshots/current-20260922/carteira.png)               | 240 títulos fictícios, filtros e paginação                                |
| [Título](screenshots/current-20260922/titulo.png)                   | Saldo de TIT-0001, R$ 1.217,39, situação, ações e dados do título         |
| [Importações](screenshots/current-20260922/importacoes.png)         | Área de escolha do CSV e regras de formato; nada foi importado na captura |
| [Lembretes](screenshots/current-20260922/lembretes.png)             | Fila simulada e acesso a tentativas; processamento não alterado           |
| [Resumo no celular](screenshots/current-20260922/resumo-mobile.png) | Somente posição em aberto, vencido e em dia, em 358×610 px                |

As telas foram inspecionadas visualmente. A automação conferiu login, títulos esperados, conteúdo carregado, ausência de erros JavaScript e overflow nas seis vistas. Não efetuou pagamentos, cancelamentos, importações, reset nem envio externo. Não substitui a suíte funcional, comparação pixel a pixel com baseline, leitor de tela ou auditoria de acessibilidade integral.

## Comparação de UI/UX em 12/10/2026

A baseline `1776b97bf13b` foi servida em produção sobre `61c1c7b`, em um projeto Compose exclusivo desta revisão e acesso loopback. A coleta `before-4` contém 46 capturas: nove estados em 320, 390, 768, 1024 e 1440 CSS px, além de um estado vazio em 390 px. Ela amplia o primeiro lote válido de 31 imagens, incluindo outras áreas da aplicação. As duas primeiras coletas falharam em seletores de tipo/valor do pagamento; seus artefatos privados foram conservados.

A inspeção de 16 originais constatou saldo e situação fora da área visível da carteira em 768 e 1024 px. Esse achado P2 orientou a reorganização das linhas da carteira e dos relatórios até 1100 px. O menu móvel mantém seu limite de 900 px. A inspeção de 16 imagens finais não encontrou bloqueio visual nesses recortes; a correção também foi exercitada nas jornadas.

As capturas pareadas vieram do Edge 155.0.4283.45. O runtime e as imagens pertencem a `02eca5b7cf23`; os testes finais de `63687d0b0d53` reutilizam essas imagens por ID imutável. Fontes da aplicação e locks são idênticos entre as rodadas: mudou apenas o teste que reabre filtros após seu recolhimento automático.

O conjunto compara o seed de 240 títulos com três títulos UIUX do mesmo cliente fictício de nome longo. Esses três títulos somam R$ 2.000,00 original, R$ 500,10 recebido e R$ 1.499,90 de saldo. Em UIUX-001, original R$ 1.250,09, recebido R$ 500,10 e saldo R$ 749,99 permitem conferir a prévia de uma nova parcela. Valores da fixture não são resultados de uso por uma empresa.

Antes e depois têm 243 títulos, 61 clientes, 49 recebimentos e cinco lotes, incluindo quatro importações da fixture. O Resumo conserva R$ 516.653,77 em aberto, em 195 títulos, e R$ 118.316,93 recebidos, em 49 recebimentos, nas cinco larguras. O hash da fixture é o mesmo; instantes reais de geração, auditoria e registro diferem, como esperado. O worker visual não foi iniciado.

| Comparação | Antes | Depois |
| --- | --- | --- |
| Resumo em 1440 px | [Baseline](screenshots/uiux-20261012/before/resumo-1440.png) | [Candidato](screenshots/uiux-20261012/after/resumo-1440.png) |
| Confirmação em 1440 px | [Baseline](screenshots/uiux-20261012/before/parcela-1440.png) | [Candidato](screenshots/uiux-20261012/after/parcela-1440.png) |
| Confirmação em 320 px | [Baseline](screenshots/uiux-20261012/before/parcela-320.png) | [Candidato](screenshots/uiux-20261012/after/parcela-320.png) |
| Carteira em 768 px | [Baseline](screenshots/uiux-20261012/before/carteira-768.png) | [Candidato](screenshots/uiux-20261012/after/carteira-768.png) |
| Extrato em 390 px | [Baseline](screenshots/uiux-20261012/before/extrato-390.png) | [Candidato](screenshots/uiux-20261012/after/extrato-390.png) |
| Aging em 320 px | [Baseline](screenshots/uiux-20261012/before/aging-320.png) | [Candidato](screenshots/uiux-20261012/after/aging-320.png) |

O [registro da revisão](uiux-20261012.md) descreve os resultados e limites. Axe-core analisou 46 estados finais: zero violações e três resultados inconclusivos de contraste em parágrafos da prévia, nas larguras de 1440, 1024 e 768 px, conservados no registro. Alterar viewport ou ampliar texto por CSS não comprova zoom nativo; leitor de tela não foi verificado. Nenhuma imagem desta rodada renova a data das provas financeiras ou de restauração anteriores.

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

## Evolução de 12/10/2026

As cinco capturas de `screenshots/restore-proof/6e75361b018645ffa98bce7ad338d4d4/` vieram do navegador real durante a [restauração final](restore-proof.md#cenário-de-parcelas--candidato-de-12102026). Mostram as telas alteradas de lembrete, título integral, título parcial, extrato e aging. A viewport é 1440×1080; os PNGs conservam a página inteira, sem edição de pixels, e ficam em links na documentação. O [manifesto](evidence/restore-proof/6e75361b018645ffa98bce7ad338d4d4/manifest.json) registra fontes congeladas, imagens, hashes e resultados.

O [coletor](../scripts/capture_restore_story.cjs) só consulta após login e exige os totais/linhas prontos antes das capturas dos relatórios. A inspeção visual confirmou original R$ 125, recebido R$ 75 e saldo R$ 50 no extrato; aging inclui apenas o saldo residual do título parcial. Importações permaneceram sem novas capturas nesta evolução. As imagens de `1054efee…` foram preservadas: sua prova financeira passou, mas extrato e aging ainda carregavam ao capturar; elas não representam relatórios prontos. As pastas de 22/09/2026 continuam históricas.
