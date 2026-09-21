# Dados de demonstração
Origem: gerador próprio, clientes inventados identificados como fictícios, emails example.com. Sem CPF, telefone, boleto ou dados reais.
CSV UTF-8 (BOM aceito), vírgula, aspas CSV padrão; até 2 MiB e 5.000 registros. Cabeçalho: source_system,external_receivable_id,external_customer_id,customer_name,customer_email,description,amount_brl,due_date.
amount_brl: string decimal com ponto, positiva, no máximo duas casas, sem sinal/expoente/milhar. Exemplo 1250.09. Datas civis ISO. Espaços externos removidos; IDs sensíveis a maiúsculas. Campos desconhecidos e cabeçalhos duplicados rejeitados.
Comparação considera nome/email do cliente e todos os campos importados do título. Duplicata idêntica não altera estado financeiro. Conflitos bloqueiam o lote inteiro; linhas de diagnóstico permanecem.
O gerador padrão usa seed 42, versão 1, referência 2026-08-17, 60 clientes e 240 títulos. Manifesto acompanha o CSV. Fixture manual separada contém centavos verificáveis sem reutilizar o algoritmo.


Limites de texto após trim: `source_system` 80; IDs externos 100 cada; `customer_name` 200; `customer_email` 254 e sintaxe válida; `description` 500. Esses campos são obrigatórios. Datas aceitam 0001-01-01 a 9999-12-31, com validação do calendário. O valor máximo é 9223372036854775807 centavos.

Campos entre aspas podem conter vírgulas, aspas escapadas e quebras de linha. Linhas fisicamente vazias entre registros são ignoradas e não consomem o limite de 5.000 registros. `line` nos diagnósticos identifica a linha física onde o registro começa, inclusive após campos com múltiplas linhas ou linhas vazias; `line=0` indica erro do arquivo como um todo. A prévia da interface exibe 50 registros por página e preserva todos os diagnósticos (também paginados quando necessário).
