# Segurança e atualização do banco

Esta aplicação demonstra uma empresa fictícia em uma máquina local. O controle de segurança foi revisto em 21/09/2026; isso não equivale a uma certificação para publicação na internet.

## Login

Fontes do contrato local: [`login_admission.py`](../backend/src/gestao_recebiveis/login_admission.py), [`auth.py`](../backend/src/gestao_recebiveis/auth.py). Conferência documental em **22/09/2026**; regras da implementação, não medição de produção.

O PostgreSQL persiste a admissão antes do Argon2, em transação própria. Um erro 401 não remove a tentativa. Há cinco reservas por conta normalizada + origem e trinta por origem, em janelas de 60 segundos iniciadas na primeira reserva. A resposta excedente é 429 com `Retry-After`. Uma reserva bem-sucedida é liberada, sem apagar outras falhas concorrentes. O advisory lock da origem coordena múltiplos processos de API.

Uma conta esgotada é recusada antes de consumir a cota da origem. Não existe um contador global, nem bloqueio da mesma conta em outra origem. As chaves são HMAC de identidade/origem com o segredo da sessão; contadores antigos são removidos durante novas admissões. O horário vem do banco, independentemente do relógio comercial da demo. Rotacionar `SESSION_SECRET` invalida sessões e muda essas chaves.

O Compose inicia Uvicorn com `--no-proxy-headers`: um cliente não pode escolher sua origem enviando `X-Forwarded-For`. Na demonstração, o Next.js faz o encaminhamento e aparece como uma origem compartilhada. Isso protege a CPU local, mas usuários atrás do mesmo proxy/NAT dividem a cota; variar contas pode esgotá-la. Para uma implantação pública, configure uma borda que substitua headers encaminhados por informações verificadas e limite por cliente. Não habilite confiança irrestrita em `X-Forwarded-For`. O comando efetivo está no [Compose](../compose.yaml), conferido em **22/09/2026**. A [referência do Uvicorn](https://www.uvicorn.org/settings/) ficou indisponível na reconsulta dessa data; não foi usada como nova confirmação externa.

## Privilégios do banco

Fontes do contrato local: [`provision_database.py`](../backend/src/gestao_recebiveis/provision_database.py). Conferência documental em **22/09/2026**; regras da implementação, não medição de produção.

| Serviço            | Papel PostgreSQL                                              | Credencial                |
| ------------------ | ------------------------------------------------------------- | ------------------------- |
| `db` e `db-init`   | `gestao_recebiveis` (bootstrap administrador)                 | `DATABASE_PASSWORD`       |
| `migrate`          | `gestao_owner`, proprietário das tabelas e sequências         | `DATABASE_OWNER_PASSWORD` |
| API, worker e seed | `gestao_app`, SELECT/INSERT/UPDATE/DELETE e uso de sequências | `DATABASE_APP_PASSWORD`   |

Owner e runtime não têm superuser, criação de bancos/papéis, replicação ou bypass de RLS. O runtime não é membro do owner, não pode criar tabelas no schema público nem alterar `alembic_version`. A credencial administrativa não é injetada em API, worker ou migrate. O seed pode modificar os dados fictícios, mas não o schema.

`db-init` é idempotente: cria/atualiza os dois papéis, transfere a propriedade das tabelas conhecidas e respectivas sequências, e define concessões para tabelas futuras criadas pelo owner. Isso é necessário porque [privilégios padrão](https://www.postgresql.org/docs/current/sql-alterdefaultprivileges.html) (consulta: 22/09/2026) se aplicam aos objetos criados pelo papel indicado, não retroativamente aos objetos antigos. A conta administrativa continua existindo para backup/restore; proteja o `.env`, o host e o socket Docker.

## Atualizar uma instalação existente sem apagar dados

Fontes do contrato local: [`provision_database.py`](../backend/src/gestao_recebiveis/provision_database.py). Conferência documental em **22/09/2026**; regras da implementação, não medição de produção.

Mantenha a mesma versão/família da imagem PostgreSQL do volume existente. A troca anterior Debian → Alpine continua exigindo o procedimento separado de [migração lógica](verification.md#banco-de-versões-anteriores).

1. Pare os escritores com `docker compose stop api worker`. Faça backup lógico e confirme que consegue restaurá-lo em outro banco. Preserve o `.env` e o volume originais.
2. Mantenha `DATABASE_PASSWORD` exatamente como está. Acrescente `DATABASE_OWNER_PASSWORD` e `DATABASE_APP_PASSWORD` com valores aleatórios independentes de pelo menos 24 caracteres, preferencialmente hexadecimais. O script PowerShell acrescenta essas variáveis ausentes automaticamente ao iniciar; não substitui o segredo antigo.
3. Construa a API e inicie o banco: `docker compose build api` e `docker compose up -d --wait db`.
4. Execute `docker compose run --rm migrate`. A dependência `db-init` provisiona os papéis e transfere a propriedade dos objetos conhecidos; a migração acrescenta somente `login_admission`. Não use `--no-deps` nesta etapa.
5. Inicie `docker compose up -d --wait api worker frontend`. Confira login, carteira, totais e processamento. Não rode `seed` em uma carteira importada só para efetuar esta atualização.

Nenhum passo remove volumes ou trunca dados. `down --volumes` e `reset` não fazem parte da atualização. `db-init` reaplica as senhas definidas no `.env`; ao rotacioná-las, pare API/worker, reprovisione e recrie os serviços para não manter conexões com credenciais antigas.

## Evidência e limites

Fontes do contrato local: [`test_database_roles.py`](../backend/src/gestao_recebiveis/../../tests/test_database_roles.py), [`test_login_admission.py`](../backend/src/gestao_recebiveis/../../tests/test_login_admission.py). Conferência documental em **22/09/2026**; regras da implementação, não medição de produção.

Os testes de banco usam o runtime restrito para executar a lógica e o owner somente para limpar fixtures/migrar. As regressões verificam negação de DDL, alteração de versão, criação de papel e `SET ROLE`, além de persistência de 401, concorrência e isolamento de cotas. O probe `backend/tests/database_upgrade_probe.py` inicia no schema anterior, sem apagar um banco preexistente, repete o provisionamento e verifica usuários, clientes, títulos, total pago e propriedade de sequências. Ele exige banco vazio com sufixo `_test`.

O controle não contém autenticação federada, MFA, recuperação de senha nem proteção distribuída de borda. O papel runtime ainda pode alterar dados da aplicação, como necessário ao produto; uma execução arbitrária dentro da API continuaria sendo grave. Uma configuração local e testes finitos não demonstram resistência contra todos os ataques.

## Integridade e isolamento da prova de recuperação

O [ensaio de restauração](restore-proof.md) recusa modo/banco/projeto fora de seu contrato, destino ocupado e dump com checksum divergente. A limpeza exige os rótulos de propriedade do ensaio. Arquivos completos e credenciais ficam fora do repositório/OneDrive, em diretório com ACL conferida antes de escrevê-los; evidência pública contém hashes e resultados selecionados. API e banco não publicam portas nessa prova, e o frontend temporário é acessível somente em loopback. O runtime restrito foi novamente verificado com negações reais de operações administrativas.

Um hash local detecta divergência do arquivo em relação ao manifesto; quem puder alterar ambos pode substituí-los. Não há assinatura, criptografia do backup nem validação de cópia externa neste resultado. Procedimento proposto e condições para provedor/armazenamento externo estão no [plano de integração](provider-integration-plan.md).
