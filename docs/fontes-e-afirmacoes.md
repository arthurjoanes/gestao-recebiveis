# Fontes e afirmações — Gestão de recebíveis

## Como ler a conferência

**Data da revisão documental: 22/09/2026.** Código, contratos e configuração foram confrontados com as fontes locais indicadas; números históricos foram conferidos nos artefatos preservados. A data de conferência não substitui a data da execução. Exemplos sintéticos, configurações padrão, observações históricas e propostas futuras têm naturezas diferentes.

Esta revisão não reexecutou a aplicação, suítes de backend/navegador, scans de segurança, restauração ou estudos de usuários. Os números de testes continuam restritos aos commits/ambientes originais. Links para código/testes mostram regra e critério; não significam que o teste foi executado agora. Valores ilustrativos não comprovam resultado comercial.

## Regras e configuração atuais

| Afirmação                                                                                  | Conclusão e fonte primária                                                                                                                                                                                        | Data / limite                                                        |
| ------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Identidade do título é origem + código externo; lote conflitante não confirma parcialmente | [Unicidade](../backend/src/gestao_recebiveis/models.py), [comparação e transação](../backend/src/gestao_recebiveis/imports.py) e [critérios financeiros](../backend/tests/test_financial.py) sustentam o contrato | Conferido em 22/09/2026; não demonstra entradas ilimitadas           |
| Baixa integral e idempotente                                                               | [Schema](../backend/src/gestao_recebiveis/schemas.py) não aceita valor parcial; [pay](../backend/src/gestao_recebiveis/receivables.py) usa valor bloqueado, chave e conteúdo                                      | Conferido em 22/09/2026                                              |
| CSV: 2 MiB, 5.000 registros, campos e calendário limitados                                 | Constantes e validações em [import_csv.py](../backend/src/gestao_recebiveis/import_csv.py); [matriz](../backend/tests/test_field_matrix.py)                                                                       | Conferido em 22/09/2026; limites locais, não limite universal do CSV |
| Corpo multipart acrescenta 64 KiB; JSON admite 8 KiB                                       | [Middleware](../backend/src/gestao_recebiveis/request_limits.py)                                                                                                                                                  | Conferido em 22/09/2026                                              |
| Valores em centavos inteiros; até 9.223.372.036.854.775.807                                | [Parser](../backend/src/gestao_recebiveis/import_csv.py) e [modelo](../backend/src/gestao_recebiveis/models.py)                                                                                                   | Conferido em 22/09/2026; máximo contratual, não venda real           |
| 60 clientes, 240 títulos, seed 42 e referência 17/08/2026                                  | Defaults do [gerador](../backend/src/gestao_recebiveis/generator.py) e [seed](../backend/src/gestao_recebiveis/seed.py)                                                                                           | Conferido em 22/09/2026; carteira pode mudar após ações do operador  |
| Três títulos da amostra somam R$ 2.000,00                                                  | Soma decimal de [valid.csv](../data/samples/valid.csv): 1.250,09 + 480,10 + 269,81                                                                                                                                | Recalculado em 22/09/2026; massa separada da prova de R$ 125         |
| Login: 5 reservas por conta/origem, 30 por origem, janela de 60 s                          | Constantes e transação em [login_admission.py](../backend/src/gestao_recebiveis/login_admission.py); [teste](../backend/tests/test_login_admission.py)                                                            | Conferido em 22/09/2026; proxy compartilha origem                    |
| Fila: lease 60 s, renovação 20 s, até 5 tentativas por padrão                              | [Configuração](../backend/src/gestao_recebiveis/config.py), [política](../backend/src/gestao_recebiveis/reminders/policy.py) e [serviço](../backend/src/gestao_recebiveis/reminders/service.py)                   | Conferido em 22/09/2026; ambiente pode alterar defaults              |
| O provedor é simulado e persiste no mesmo banco                                            | [FakeProvider](../backend/src/gestao_recebiveis/reminders/provider.py)                                                                                                                                            | Conferido em 22/09/2026; não comprova entrega externa                |
| Pool até 10 conexões; espera/conexão/lock de 5 s e statement de 15 s                       | [create_engine](../backend/src/gestao_recebiveis/database.py)                                                                                                                                                     | Conferido em 22/09/2026; não é prazo total da transação              |
| Serviços em loopback; PostgreSQL 18.6; Python 3.13.15; Node 24.19.0                        | [Compose](../compose.yaml), [banco](../database/Dockerfile), [backend](../backend/Dockerfile), [frontend](../frontend/Dockerfile)                                                                                 | Conferido em 22/09/2026; versões declaradas, sem novo build          |

## Observações históricas

| Dado apresentado                                                                | Fonte primária e conclusão                                                                                                                | Data / limite                                                                                        |
| ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Restauração: R$ 125 importados, R$ 50 pagos e R$ 75 abertos, mesmas identidades | [Manifesto `11adf9df…`](evidence/restore-proof/11adf9df35ba4314945ffdd4fbaeabfc/manifest.json); valores e igualdade reconsultados no JSON | Executado em 22/09/2026; conferido no arquivo em 22/09/2026, sem novo restore                        |
| 15 casos Playwright, 14 jornadas + 1 formatação, sem falha/skip/retry           | [Recibo do CI](evidence/frontend-ci-20260922.json), commit `5718cdad`                                                                     | 22/09/2026; não prova toda acessibilidade ou desempenho                                              |
| 158 testes backend e revisão de dependências/segredos                           | [Recibo de portfólio](evidence/portfolio-review-20260922.json)                                                                            | 22/09/2026; ambientes/tempos e falhas anteriores permanecem no recibo e [histórico](verification.md) |
| Capturas de estados financeiros                                                 | [capture.json](screenshots/current-20260922/capture.json), fonte `deade1369`                                                              | 22/09/2026; captura não substitui consulta/prova de identidade                                       |
| IBM Plex local soma 130.080 bytes em dois WOFF2                                 | [Arquivos e hashes](../frontend/src/app/fonts/sources.json), contagem dos bytes locais                                                    | Recalculado em 22/09/2026; não mede transferência, LCP ou interação                                  |
| Roteiro de cinco minutos e ensaio em 5–8 minutos                                | [Roteiro](demo.md) é estimativa de apresentação                                                                                           | Sem medição publicada; não é promessa de duração                                                     |

A consulta à API pública do GitHub em **22/09/2026** confirmou `conclusion=success` e o mesmo SHA do [recibo de CI](evidence/frontend-ci-20260922.json). Isso valida a identidade e conclusão daquele run, sem repetir seus testes.

## Referências externas

| Referência                                                                                                                                                          | O que sustenta                                                                                                       | Consulta                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| [PostgreSQL — SELECT/locks](https://www.postgresql.org/docs/current/sql-select.html) e [unicidade](https://www.postgresql.org/docs/current/indexes-unique.html)     | Semântica dos mecanismos usados; o efeito local depende das transações do projeto                                    | 22/09/2026                                                  |
| [PostgreSQL — privilégios padrão](https://www.postgresql.org/docs/current/sql-alterdefaultprivileges.html)                                                          | Defaults aplicam-se a objetos futuros do papel indicado; provisionamento local trata os existentes                   | 22/09/2026                                                  |
| [Stripe — idempotência](https://docs.stripe.com/api/idempotent_requests)                                                                                            | Exemplo externo de contrato de repetição; não é integração implementada                                              | 22/09/2026                                                  |
| [FastAPI — testes](https://fastapi.tiangolo.com/tutorial/testing/) e [Next.js — rewrites](https://nextjs.org/docs/app/api-reference/config/next-config-js/rewrites) | Ferramentas HTTP/proxy, sem promessa de resultado deste repositório                                                  | 22/09/2026                                                  |
| [Uvicorn — configuração](https://www.uvicorn.org/settings/)                                                                                                         | Referência preexistente indisponível na reconsulta; o argumento efetivo foi confirmado no [Compose](../compose.yaml) | Falha de acesso em 22/09/2026; sem nova confirmação externa |

As referências visuais, com data e interpretação autoral, permanecem em [frontend-quality.md](frontend-quality.md). Reconsultados em 22/09/2026: Stripe Invoicing, SolidInvoice, Linear, Carbon, Atlassian, Radix, Pentagram, Behance/Swavee, React e W3C. A disponibilidade dessas páginas não certifica acessibilidade ou usabilidade deste produto.

## Ajustes desta revisão

- Arquitetura visível no README, com fontes de componentes e fronteiras; ordem comum aos seis projetos.
- Contratos HTTP e CSV reorganizados em rotas, objetos, tabelas e limites com fontes por seção.
- Números de CI/backend separados por recibo; não atribuídos à edição documental.
- Durações de apresentação mantidas como estimativas. Material de restauração e `data/README.md` ligado à prova preservados byte a byte.

## Cobertura documental

Todos os Markdown vivos abaixo foram revisados quanto a hierarquia, contratos, números, proveniência, data e links. Referências e datas ficam também junto às seções correspondentes.

| Documento                                                         | Escopo da revisão                                            |
| ----------------------------------------------------------------- | ------------------------------------------------------------ |
| [README.md](../README.md)                                         | Apresentação, arquitetura e resumo com fontes                |
| [docs/api-contract.md](api-contract.md)                           | Contrato, configuração ou critérios locais; fontes por seção |
| [docs/architecture.md](architecture.md)                           | Contrato, configuração ou critérios locais; fontes por seção |
| [docs/data-contract.md](data-contract.md)                         | Contrato, configuração ou critérios locais; fontes por seção |
| [docs/decisoes-tecnicas.md](decisoes-tecnicas.md)                 | Guia, decisões ou histórico; data e alcance explicitados     |
| [docs/demo.md](demo.md)                                           | Guia, decisões ou histórico; data e alcance explicitados     |
| [docs/frontend-quality.md](frontend-quality.md)                   | Guia, decisões ou histórico; data e alcance explicitados     |
| [docs/image-captures.md](image-captures.md)                       | Guia, decisões ou histórico; data e alcance explicitados     |
| [docs/problem-solution.md](problem-solution.md)                   | Guia, decisões ou histórico; data e alcance explicitados     |
| [docs/provider-integration-plan.md](provider-integration-plan.md) | Contrato, configuração ou critérios locais; fontes por seção |
| [docs/restore-proof.md](restore-proof.md)                         | Guia, decisões ou histórico; data e alcance explicitados     |
| [docs/security.md](security.md)                                   | Guia, decisões ou histórico; data e alcance explicitados     |
| [docs/verification.md](verification.md)                           | Guia, decisões ou histórico; data e alcance explicitados     |

Registros históricos, licenças e material ligado por hash foram conferidos como fontes, mas não reformatados. O [padrão documental](padrao-documentacao.md) define a ordem e como manter novas afirmações rastreáveis.
