# Requisitos e escopo vigente — ciclo inicial

Busca geral com compreensão semântica, filtros obrigatórios e ordenação conforme a demanda, sem lista global restritiva de fontes.

Definido a partir das decisões de Pedro até 06/11/2026. Documento de planejamento; não comprova implementação, treinamento, revisão ou aceite. As alterações são propostas no PR de organização, sem merge por agente.

## Requisitos funcionais

| ID  | Resultado exigido                                                                                                                       |
| --- | --------------------------------------------------------------------------------------------------------------------------------------- |
| F01 | Expor consulta, filtros, ordenação, paginação e evidências por MCP, em fontes pertinentes à demanda do consumidor.                      |
| F02 | Distinguir categoria, atributos, condições obrigatórias e preferências, preservando interseção e negação dos critérios.                 |
| F03 | Descobrir capacidades de filtro da fonte e aplicar filtros nativos por API/conector ou navegação autorizada quando disponíveis.         |
| F04 | Verificar pós-busca os filtros obrigatórios e explicitar critérios não verificáveis; não relaxar filtros sem instrução do usuário.      |
| F05 | Pesquisar ofertas de Mercado Livre, SHEIN e fontes adicionais por adaptador, normalizando produto, variante, loja, preço e condições.   |
| F06 | Filtrar avaliação do produto/vendedor e número de avaliações conforme critérios explícitos; não inventar o significado de bem avaliado. |
| F07 | Ordenar resultados comparáveis por preço ou outro critério pedido, distinguindo preço do item, frete, moeda e descontos condicionais.   |
| F08 | Buscar documentos, pesquisas e informação geral com filtros de origem, data, idioma, tipo, autor e relevância quando demandados.        |
| F09 | Deduplicar variantes/ofertas e percorrer páginas com limites e cobertura declarados, preservando evidência e instante da coleta.        |
| F10 | Fornecer fontes originais e trilha dos filtros aplicados para verificação independente pelo agente de Validação.                        |

## Requisitos não funcionais

| ID  | Critério                                                                                                                                                                                                                                                                                                              |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| N01 | Contribuição rastreável por issue/branch/PR; somente Pedro revisa/aprova PRs e aceita issues, sem merge/auto-merge/deploy de agentes. Durante a semana, dependência tecnicamente disponível em branch/PR validado pode ser consumida provisoriamente em PR empilhado; revisão/aceite/merge ficam com Pedro no sábado. |
| N02 | Contratos versionados, entradas/saídas validadas e erros explícitos; dados externos nunca concedem permissões.                                                                                                                                                                                                        |
| N03 | Sem serviço pago obrigatório, faturamento ou fallback remoto automático; executar ferramentas/caches no C: e respeitar pausas.                                                                                                                                                                                        |
| N04 | Testes de sucesso/erro e avaliações reais reproduzíveis; registrar versões e distinguir mock, execução e aceite humano.                                                                                                                                                                                               |
| N05 | Minimização de dados, credenciais fora do Git, acesso mínimo e retenção/exclusão definidas; não publicar dados reais de usuários.                                                                                                                                                                                     |
| N06 | Limites de entrada, memória, concorrência e tempo configuráveis, cancelamento e falha fechada; medir desempenho no hardware disponível.                                                                                                                                                                               |
| N07 | Documentação operacional coerente com código e evidências; disponibilidade ou qualidade não podem ser inferidas de um perfil ou schema.                                                                                                                                                                               |
| N08 | Até cinco sprints de entrega + uma de validação/mudanças, cada uma até uma semana; estimativas PP/P/M/L=1/2/4/8 e meta mínima de 8 unidades/dia por projeto ativo.                                                                                                                                                    |

## Fora do ciclo

- Compra, pagamento, alteração de conta ou publicação de conteúdo.
- Promessa de cobrir todos os sites já no primeiro ciclo.
- Relaxamento silencioso de filtro obrigatório.
- Tratar resultado de Busca como informação já validada.

## Verificação e aceite

Cada requisito é rastreado em TRACEABILITY.md, com critérios concretos no corpo das issues. Dados conhecidos/sintéticos e ferramentas determinísticas verificam resultados quando possível; comportamento generativo exige casos separados e revisão apropriada. Não usar um teste de roteamento, presença de perfil ou metadado para alegar competência ou treino. Não declarar cobertura completa quando há pendência de ambiente/fonte.

A meta de 8 unidades/dia é um mínimo desejado por projeto ativo, não um teto de esforço nem uma medição de inteligência. A duração semanal é o objetivo do plano; a capacidade real e os bloqueios precisam ser observados e reportados. Não fabricar tarefa/estimativa/aceite para cumprir calendário.
