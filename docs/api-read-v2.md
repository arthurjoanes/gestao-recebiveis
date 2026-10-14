# Consultas com histórico limitado — v2

O frontend usa `GET /api/v2/receivables`, `/api/v2/reports/aging`, `/api/v2/customers/{id}/statement` e `/api/v2/receivables/{id}`. Autenticação, mutações e demais recursos continuam em v1, com as mesmas permissões e proteções CSRF. Não há migração de dados para essa mudança.

Na v2, títulos de listas e relatórios são resumos: não contêm `payments`. `paid_cents`, `remaining_cents` e `payment_state` continuam calculados sobre todos os recebimentos. O extrato mantém sua página independente de recebimentos.

O detalhe conserva os arrays `payments`, `events` e `reminders`, agora limitados a 20 itens por coleção. Os parâmetros `payment_page`, `event_page` e `reminder_page` começam em 1; `page_size` permite 1 a 100 itens. `history` informa `total`, `page` e `page_size` de cada coleção. Saldos e contagens independem da página selecionada. Eventos e lembretes seguem IDs crescentes; recebimentos têm ordem estável. Paginação consulta a posição atual, não congela alterações entre requisições.

Os endpoints v1 permanecem para compatibilidade, inclusive seu histórico completo. Consumidores novos devem usar v2; a garantia de payload limitado aplica-se à v2. Para migrar um cliente, retire a leitura de `payments` das listas e use o detalhe paginado. A remoção futura da v1 exigirá anúncio separado. O campo singular `payment` continua identificando o único recebimento, quando existe exatamente um.
