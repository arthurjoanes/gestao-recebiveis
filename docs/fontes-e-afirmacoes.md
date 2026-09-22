# Fontes e afirmações — Gestão de recebíveis

## Como ler a conferência

**Revisão das fontes: 22/09/2026.** Este registro reúne as referências do código, das decisões e dos resultados publicados. As datas nas tabelas identificam execuções, capturas e consultas de preços, não atualizações editoriais.

Os resultados de testes pertencem aos commits e ambientes indicados nos artefatos. Links para código e testes descrevem regras e critérios; exemplos sintéticos não comprovam resultados comerciais.

## Regras e configuração atuais

| Afirmação                                                                                  | Conclusão e fonte primária                                                                                                                                                                                        | Limite                                      |
| ------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| Identidade do título é origem + código externo; lote conflitante não confirma parcialmente | [Unicidade](../backend/src/gestao_recebiveis/models.py), [comparação e transação](../backend/src/gestao_recebiveis/imports.py) e [critérios financeiros](../backend/tests/test_financial.py) sustentam o contrato | Não demonstra entradas ilimitadas           |
| Baixa integral e idempotente                                                               | [Schema](../backend/src/gestao_recebiveis/schemas.py) não aceita valor parcial; [pay](../backend/src/gestao_recebiveis/receivables.py) usa valor bloqueado, chave e conteúdo                                      | —                                           |
| CSV: 2 MiB, 5.000 registros, campos e calendário limitados                                 | Constantes e validações em [import_csv.py](../backend/src/gestao_recebiveis/import_csv.py); [matriz](../backend/tests/test_field_matrix.py)                                                                       | Limites locais, não limite universal do CSV |
| Corpo multipart acrescenta 64 KiB; JSON admite 8 KiB                                       | [Middleware](../backend/src/gestao_recebiveis/request_limits.py)                                                                                                                                                  | —                                           |
| Valores em centavos inteiros; até 9.223.372.036.854.775.807                                | [Parser](../backend/src/gestao_recebiveis/import_csv.py) e [modelo](../backend/src/gestao_recebiveis/models.py)                                                                                                   | Máximo contratual, não venda real           |
| 60 clientes, 240 títulos, seed 42 e referência 17/08/2026                                  | Defaults do [gerador](../backend/src/gestao_recebiveis/generator.py) e [seed](../backend/src/gestao_recebiveis/seed.py)                                                                                           | Carteira pode mudar após ações do operador  |
| Três títulos da amostra somam R$ 2.000,00                                                  | Soma decimal de [valid.csv](../data/samples/valid.csv): 1.250,09 + 480,10 + 269,81                                                                                                                                | Massa separada da prova de R$ 125           |
| Login: 5 reservas por conta/origem, 30 por origem, janela de 60 s                          | Constantes e transação em [login_admission.py](../backend/src/gestao_recebiveis/login_admission.py); [teste](../backend/tests/test_login_admission.py)                                                            | Proxy compartilha origem                    |
| Fila: lease 60 s, renovação 20 s, até 5 tentativas por padrão                              | [Configuração](../backend/src/gestao_recebiveis/config.py), [política](../backend/src/gestao_recebiveis/reminders/policy.py) e [serviço](../backend/src/gestao_recebiveis/reminders/service.py)                   | Ambiente pode alterar defaults              |
| O provedor é simulado e persiste no mesmo banco                                            | [FakeProvider](../backend/src/gestao_recebiveis/reminders/provider.py)                                                                                                                                            | Não comprova entrega externa                |
| Pool até 10 conexões; espera/conexão/lock de 5 s e statement de 15 s                       | [create_engine](../backend/src/gestao_recebiveis/database.py)                                                                                                                                                     | Não é prazo total da transação              |
| Serviços em loopback; PostgreSQL 18.6; Python 3.13.15; Node 24.19.0                        | [Compose](../compose.yaml), [banco](../database/Dockerfile), [backend](../backend/Dockerfile), [frontend](../frontend/Dockerfile)                                                                                 | Versões declaradas, sem novo build          |

## Observações históricas

| Dado apresentado                                                                | Fonte primária e conclusão                                                                                                               | Data / limite                                                                                        |
| ------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Restauração: R$ 125 importados, R$ 50 pagos e R$ 75 abertos, mesmas identidades | [Manifesto `11adf9df…`](evidence/restore-proof/11adf9df35ba4314945ffdd4fbaeabfc/manifest.json); valores e identidade registrados no JSON | Executado em 22/09/2026; não é uma nova restauração                                                  |
| 15 casos Playwright, 14 jornadas + 1 formatação, sem falha/skip/retry           | [Recibo do CI](evidence/frontend-ci-20260922.json), commit `5718cdad`                                                                    | 22/09/2026; não prova toda acessibilidade ou desempenho                                              |
| 158 testes backend e revisão de dependências/segredos                           | [Recibo de portfólio](evidence/portfolio-review-20260922.json)                                                                           | 22/09/2026; ambientes/tempos e falhas anteriores permanecem no recibo e [histórico](verification.md) |
| Capturas de estados financeiros                                                 | [capture.json](screenshots/current-20260922/capture.json), fonte `deade1369`                                                             | 22/09/2026; captura não substitui consulta/prova de identidade                                       |
| IBM Plex local soma 130.080 bytes em dois WOFF2                                 | [Arquivos e hashes](../frontend/src/app/fonts/sources.json), contagem dos bytes locais                                                   | Não mede transferência, LCP ou interação                                                             |
| Roteiro de cinco minutos e ensaio em 5–8 minutos                                | [Roteiro](demo.md) é estimativa de apresentação                                                                                          | Sem medição publicada; não é promessa de duração                                                     |

## Referências externas

| Referência                                                                                                                                                          | O que sustenta                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [PostgreSQL — SELECT/locks](https://www.postgresql.org/docs/current/sql-select.html) e [unicidade](https://www.postgresql.org/docs/current/indexes-unique.html)     | Semântica dos mecanismos usados; o efeito local depende das transações do projeto                                                                                                 |
| [PostgreSQL — privilégios padrão](https://www.postgresql.org/docs/current/sql-alterdefaultprivileges.html)                                                          | Defaults aplicam-se a objetos futuros do papel indicado; provisionamento local trata os existentes                                                                                |
| [Stripe — idempotência](https://docs.stripe.com/api/idempotent_requests)                                                                                            | Exemplo externo de contrato de repetição; não é integração implementada                                                                                                           |
| [FastAPI — testes](https://fastapi.tiangolo.com/tutorial/testing/) e [Next.js — rewrites](https://nextjs.org/docs/app/api-reference/config/next-config-js/rewrites) | Ferramentas HTTP/proxy, sem promessa de resultado deste repositório                                                                                                               |
| [Uvicorn — configuração](https://www.uvicorn.org/settings/)                                                                                                         | Referência preexistente indisponível na reconsulta; o argumento efetivo foi confirmado no [Compose](../compose.yaml). Falha de acesso em 22/09/2026; sem nova confirmação externa |

As referências visuais e sua aplicação estão em [frontend-quality.md](frontend-quality.md). São interpretações de design, não certificação de acessibilidade ou estudo de usabilidade.

## Ajustes desta revisão

- Arquitetura visível no README, com fontes de componentes e fronteiras; ordem comum aos seis projetos.
- Contratos HTTP e CSV reorganizados em rotas, objetos, tabelas e limites com fontes por seção.
- Números de CI/backend separados por recibo; não atribuídos à edição documental.
- Durações de apresentação mantidas como estimativas. Material de restauração e `data/README.md` ligado à prova preservados byte a byte.

## Cobertura documental

Guias relacionados, com contratos, exemplos e evidências detalhados:

| Documento                                                         | Conteúdo                                      |
| ----------------------------------------------------------------- | --------------------------------------------- |
| [README.md](../README.md)                                         | Apresentação, arquitetura e resumo com fontes |
| [docs/api-contract.md](api-contract.md)                           | Contrato, configuração e critérios locais     |
| [docs/architecture.md](architecture.md)                           | Contrato, configuração e critérios locais     |
| [docs/data-contract.md](data-contract.md)                         | Contrato, configuração e critérios locais     |
| [docs/decisoes-tecnicas.md](decisoes-tecnicas.md)                 | Guia, decisões e resultados históricos        |
| [docs/demo.md](demo.md)                                           | Guia, decisões e resultados históricos        |
| [docs/frontend-quality.md](frontend-quality.md)                   | Guia, decisões e resultados históricos        |
| [docs/image-captures.md](image-captures.md)                       | Guia, decisões e resultados históricos        |
| [docs/problem-solution.md](problem-solution.md)                   | Guia, decisões e resultados históricos        |
| [docs/provider-integration-plan.md](provider-integration-plan.md) | Contrato, configuração e critérios locais     |
| [docs/restore-proof.md](restore-proof.md)                         | Guia, decisões e resultados históricos        |
| [docs/security.md](security.md)                                   | Guia, decisões e resultados históricos        |
| [docs/verification.md](verification.md)                           | Guia, decisões e resultados históricos        |

Registros históricos, licenças e material ligado por hash conservam seus arquivos originais. O [padrão documental](padrao-documentacao.md) orienta a organização e a manutenção das referências.
