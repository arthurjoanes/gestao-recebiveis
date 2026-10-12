# Padrão de documentação

Guia de manutenção dos documentos do repositório. O README apresenta o projeto; os guias detalham reprodução, contratos, decisões e evidências. O [registro de fontes e afirmações](fontes-e-afirmacoes.md) reúne as referências detalhadas deste repositório.

## Ordem de leitura

| Seção do README          | Pergunta que deve responder                                              |
| ------------------------ | ------------------------------------------------------------------------ |
| Visão geral              | Que problema resolve, para quem e em qual cenário?                       |
| Demonstração             | Como a aplicação se apresenta e qual jornada pode ser conferida?         |
| Arquitetura              | Como os componentes se conectam e onde ficam as responsabilidades?       |
| Stack e decisões         | Quais tecnologias foram usadas e que escolhas exigem explicação?         |
| Executar localmente      | Quais pré-requisitos, comandos e endereço permitem reproduzir o projeto? |
| Verificação e evidências | Como testar e quais resultados possuem prova reproduzível?               |
| Limites e segurança      | Quais restrições, riscos e condições de uso permanecem?                  |
| Documentação             | Qual guia abrir para cada aprofundamento?                                |
| Autor e licença          | Quem desenvolveu, como entrar em contato e qual licença se aplica?       |

O README apresenta o problema e a aplicação antes dos detalhes de execução. Contratos, operação e testes ficam nos respectivos guias.

## Apresentação e navegação

O cabeçalho usa links de navegação com rótulos que identificam cada destino. Os SVGs são locais.

O diagrama de arquitetura fica no próprio README, acompanhado de uma explicação e de links para a implementação. A [documentação do GitHub](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams) explica a renderização de Mermaid.

Capturas devem mostrar um estado real e um recorte legível, com data e contexto. O README privilegia a página principal e a ação explicada. Imagens muito altas ficam como links para consulta; a documentação não deve reduzir uma página inteira até tornar o texto ilegível. Uma imagem de interface demonstra apresentação, enquanto resultados de cálculo, isolamento ou persistência precisam de fonte própria.

<a id="afirmações-fontes-e-datas"></a>

## Referências e evidências

Priorize uma leitura fluida. Inclua referências quando ajudam a reproduzir um resultado, consultar uma decisão ou avaliar uma alegação relevante. Não é necessário anexar fonte e data a cada frase. Links úteis podem entrar na própria prosa; as referências detalhadas ficam no guia correspondente ou no registro central.

| Informação                                    | Referência útil                                | Contexto que deve permanecer                                                                          |
| --------------------------------------------- | ---------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Comportamento, limite ou versão fixada        | Código, configuração ou guia técnico           | Link quando ajudar a entender ou reproduzir o comportamento; sem carimbo de conferência em cada seção |
| Resultado de teste, desempenho ou experimento | Artefato original, comando, cenário e ambiente | Data real da execução, revisão, amostra e condições                                                   |
| Valor de uma demonstração sintética           | Fixture, gerador ou resultado registrado       | Identificação do cenário e distinção de valores de mercado                                            |
| Preço de serviço externo                      | Página ou API oficial                          | Data da cotação, moeda, região, modalidade e unidade; distinguir estimativa de cobrança               |
| Compatibilidade ou correção de segurança      | Documentação oficial, release ou advisory      | Versões e alcance; data quando necessária para situar a informação                                    |
| Escolha de projeto ou procedimento            | Explicação da decisão e guia correspondente    | Apresentar como escolha ou instrução, sem exigir uma referência para toda decisão autoral             |

Evite repetir avisos de revisão documental ao longo do texto. Quando útil, registre a data da revisão uma única vez no documento central. Datas de capturas, testes, incidentes e preços permanecem junto ao resultado que identificam.

Corrija ou qualifique afirmações sem sustentação. Prefira fontes primárias para dados externos e resultados verificáveis. Consultar um relatório hoje não muda a data de sua execução. Artefatos históricos e protocolos vinculados por hash conservam os bytes originais; correções editoriais ficam nos documentos vivos.

## Código e manutenção

Blocos de código precisam declarar a linguagem correta, como `python`, `json`, `sql`, `yaml`, `sh` ou `powershell`. Campos e comandos curtos usam código em linha. A linguagem declarada habilita o realce do renderizador; as cores variam conforme o tema e os tokens presentes. Veja o [guia de realce do GitHub](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-and-highlighting-code-blocks).

Ao editar, confira os links relativos, as âncoras, a leitura no celular, os exemplos e a procedência das imagens. Preserve destinos existentes quando reorganizar títulos. Atualize o registro de fontes quando uma alteração mudar uma afirmação, uma tarifa, uma versão ou um resultado. O GitHub descreve propósito, uso e caminhos relativos no [guia de READMEs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes).
