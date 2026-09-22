# Gestão de recebíveis

Aplicação de contas a receber com importação CSV, pagamentos integrais e lembretes simulados. A demonstração usa dados fictícios e permite verificar repetição de requisições e recuperação de falhas.

![Resumo da carteira fictícia](docs/img/resumo.png)

Reenviar um CSV não aumenta a dívida, e repetir uma baixa não duplica o pagamento. O backend protege essas operações e registra as tentativas de lembretes para recuperar resultados incertos.

## Arquitetura

A interface envia as operações à API. O PostgreSQL guarda a carteira e a fila; um worker processa os lembretes usando um provedor fictício persistente.

```mermaid
flowchart LR
    UI[Next.js] --> API[FastAPI]
    API --> DB[(PostgreSQL)]
    Worker[Worker Python] <--> DB
    Worker --> Fake[Provedor fictício]
    Fake --> DB
```

## Decisões técnicas

- Dinheiro é armazenado em centavos e enviado como string no JSON para conservar precisão; a interface faz a conversão explicitamente.
- O CSV é revalidado na confirmação. Transações e chaves idempotentes permitem repetir baixas sem duplicar efeitos.
- A fila usa PostgreSQL com `SKIP LOCKED`, lease e heartbeat. A coordenação permanece no banco, sem exigir um broker separado.
- O provedor fictício persiste a aceitação antes de simular uma resposta perdida. Isso permite testar recuperação após reinício; a entrega por um serviço externo exige outra integração.

As [decisões técnicas](docs/decisoes-tecnicas.md) e o roteiro da [demo](docs/demo.md) estão em `docs/`.

## Rodar localmente

Use Docker Desktop com containers Linux e PowerShell 7. Python, Node e PostgreSQL executam nos containers.

Na raiz do projeto:

```powershell
.\scripts\gestao-recebiveis.ps1 setup
```

O setup gera a configuração local, constrói as imagens e carrega os dados fictícios. A interface fica em `http://localhost:3101`; a documentação da API, em `http://localhost:8101/docs`. As contas de demonstração aparecem no login.

Se você já executou a versão com PostgreSQL Debian, siga a [migração do banco](docs/verification.md#banco-de-versões-anteriores) antes de iniciar esta versão Alpine.

Sem PowerShell, copie `.env.example` para `.env`, troque `SESSION_SECRET` e `DATABASE_PASSWORD` por valores aleatórios e rode o que o script faz:

```sh
docker compose build db
docker compose build api
docker compose build frontend
docker compose up -d --wait db
docker compose run --rm --no-deps migrate
docker compose run --rm --no-deps seed
docker compose up -d --wait --wait-timeout 180 db api worker frontend
```

## Verificação

```powershell
.\scripts\gestao-recebiveis.ps1 test
.\scripts\gestao-recebiveis.ps1 proof
```

Passaram 145 testes de backend e 12 testes Playwright, além de lint, formatação e tipos. A suíte cobre importação, concorrência, permissões, pagamentos e navegação.

O `proof` é o teste de reinício do banco: interrompe o processamento após uma aceitação, reinicia seu banco descartável e verifica a recuperação sem duplicar a entrega simulada. Só existe em PowerShell (`scripts/prove.ps1`).

Os mesmos testes, com os comandos do CI (`.github/workflows/ci.yml`):

```sh
docker compose --profile test build db
docker compose --profile test build api
docker compose --profile test build frontend
docker compose --profile test build frontend-checks
docker compose --profile test build e2e
docker compose run --rm test
docker compose run --rm --no-deps frontend-checks
docker compose -f compose.yaml -f compose.e2e.yaml -p pf-gestao-recebiveis-e2e up -d --wait db
docker compose -f compose.yaml -f compose.e2e.yaml -p pf-gestao-recebiveis-e2e run --rm --no-deps migrate
docker compose -f compose.yaml -f compose.e2e.yaml -p pf-gestao-recebiveis-e2e run --rm --no-deps seed
docker compose -f compose.yaml -f compose.e2e.yaml -p pf-gestao-recebiveis-e2e up -d --wait --wait-timeout 180 api worker frontend
docker compose -f compose.yaml -f compose.e2e.yaml -p pf-gestao-recebiveis-e2e run --rm --no-deps e2e
docker compose -f compose.yaml -f compose.e2e.yaml -p pf-gestao-recebiveis-e2e --profile test --profile tools down --remove-orphans
docker compose stop db-test
```

## Limites

O escopo é uma empresa, BRL e pagamento integral. Envio externo, Pix, boleto, juros e estorno não estão implementados. Integrar um provedor real exige validar seu contrato de idempotência e reconciliação. A demonstração ainda não foi avaliada com usuários reais.

A configuração demonstrada publica os serviços em loopback. O login não limita tentativas de senha por conta ou origem; a aplicação precisa desse controle antes de atender usuários em uma rede não confiável.


Python 3.13, FastAPI, SQLAlchemy, PostgreSQL 18, Next.js 16, TypeScript e Docker. Licença MIT.
