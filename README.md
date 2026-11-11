<!-- BEGIN CURRENT PLAN 2026-11-06 -->

# sofiee-agent-search

Busca geral com compreensão semântica, filtros obrigatórios e ordenação conforme a demanda, sem lista global restritiva de fontes.

**Planejamento vigente em 06/11/2026: até 5 sprints de entrega + S6 de validação extra/mudanças.** As issues e a matriz documentam todo o ciclo; não comprovam implementação, treinamento, integração ou aceite. Preservar código e PRs existentes. Somente Pedro revisa/aprova PRs e aceita issues.

- [Requisitos e limites](docs/REQUIREMENTS.md)
- [Arquitetura e fronteiras](docs/ARCHITECTURE_PLAN.md)
- [Todas as sprints e issues](docs/DELIVERY_PLAN.md)
- [Rastreabilidade](docs/TRACEABILITY.md)
- [Execução semanal por dependências e PRs encadeados](docs/WEEKLY_EXECUTION.md)
- [Retomada diária](docs/EXECUTION_PLAN.md)
- [Contribuição](docs/CONTRIBUTION_POLICY.md)

Busca encontra fontes em qualquer lugar pertinente e preserva filtros do usuário; Validação escolhe a base adequada ao tipo de dado e verifica as referências independentemente. Não aplicar uma whitelist científica global ao Busca. O modelo pode ser compartilhado; as ferramentas e critérios de domínio são específicos.

Trabalho exclusivamente no C:, sem serviços pagos obrigatórios. SlothGeo é separado e adiado para 21/11, não um sexto agente desta rotina.
O contrato tipado de busca v1, com exemplos sintéticos e limites de validação, está em [contracts/v1](contracts/v1/README.md). Ele define a fronteira prevista; não indica runtime ou busca integrada.
- Ambiente e versões locais: [inventário reproduzível](docs/LOCAL_ENVIRONMENT.md).
<!-- END CURRENT PLAN 2026-11-06 -->

<details>
<summary>Descrição anterior da base e propostas — consultar com o estado vivo dos PRs</summary>

# Sofiee — Agente de Busca

Busca de informações para sistemas e processos de empresas.

Projeto independente da linha Sofiee, criado a pedido de Pedro em 05/11/2026. Este commit inicial registra finalidade, limites e preparação para o planejamento. Ainda não existe runtime, modelo treinado, ferramenta MCP ou integração implementada.

## Planejamento pendente

Fontes, tipos de busca, critérios de relevância, evidências e limites de acesso. Casos de uso, contratos, avaliações, arquitetura, tecnologias e sprints serão definidos com Pedro no fim de semana. Consulte [o registro de escopo](docs/ESCOPO.md).

Depois dessa definição, todas as issues de todas as sprints planejadas devem ser criadas, com dependências e critérios de aceite. O formulário de issue já está disponível neste repositório.

## Portfólio

Este é um dos quatro agentes gerais: [comunicação](https://github.com/PHnsilva/sofiee-agent-communication), [cálculo](https://github.com/PHnsilva/sofiee-agent-calculation), [validação](https://github.com/PHnsilva/sofiee-agent-validation) e [busca](https://github.com/PHnsilva/sofiee-agent-search).

[SlothEngineer](https://github.com/PHnsilva/SlothEngineer) é um sistema separado, com direção inicial de especialização em DevOps. O chat **agents** acompanha os cinco projetos.

## Contribuições

O repositório é público para consulta e sugestões por issue ou PR. Mudanças posteriores ao bootstrap usam issue, branch e PR com evidências. Revisão e aceite são de Pedro.

</details>

## Núcleo local proposto na issue #7

O runtime recebe uma consulta estruturada, preserva todos os filtros e a ordenação e entrega um plano imutável ao provedor configurado. Sem provedor, retorna `source_unavailable`; não sintetiza resultados nem remove critérios. Um provedor injetado passa por validação do contrato e coerência dos filtros obrigatórios. O limite de entrada do CLI é 80.000 bytes; detalhes e limites atuais estão em [evidência do runtime](docs/RUNTIME_EVIDENCE.md).

O adaptador Ollama local é opcional e não foi usado para uma consulta já estruturada. Não há adaptador de fonte real nesta issue; o servidor MCP interno fica na issue #8.

Comandos locais:

    C:\SDKs\Python313\python.exe -m unittest discover -s tests -v
    C:\SDKs\Python313\python.exe scripts\validate_contracts.py
    C:\SDKs\Python313\python.exe scripts\check_environment.py
    C:\SDKs\Python313\python.exe scripts\measure_runtime.py


## Servidor MCP local — issue #8

O servidor interno expõe somente as ferramentas MCP versionadas em `contracts/v1/contracts.json`. Execute com CPython 3.13.15 e as dependências exatas de `requirements.lock`: `python -m agent_runtime.mcp_server`. O transporte local usa stdio; stdout é reservado ao protocolo. Não fornece shell, caminhos de arquivo ou acesso de rede arbitrários. Operações que exigem modelo ou fonte continuam sujeitas aos limites e estados retornados pelo runtime.

## Limites MCP — issue #9

Os limites configuráveis usam valores padrão de 80.000 bytes para entrada, 65.536 bytes para saída, 30 segundos por chamada e quatro workers simultâneos. As faixas são 1.024–1.000.000 bytes para entrada/saída, 0,05–120 segundos e 1–16 workers, pelos parâmetros `SOFIEE_MCP_MAX_INPUT_BYTES`, `SOFIEE_MCP_MAX_OUTPUT_BYTES`, `SOFIEE_MCP_TIMEOUT_SECONDS` e `SOFIEE_MCP_MAX_CONCURRENCY`. Valores inválidos impedem o servidor de iniciar sem ecoar o valor recebido. Entradas, saídas e exceções não são registradas nem reproduzidas em erros. Um timeout encerra a espera do chamador, mas não mata uma função Python síncrona já iniciada; o slot permanece ocupado até ela retornar, e o limite de concorrência impede acumular workers sem limite.
