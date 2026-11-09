# Casos e protocolo de avaliação — Busca

Os arquivos development/cases.json e regression/cases.json são conjuntos públicos, sintéticos e versionados v1.0.0. Incluem uma consulta de camisa branca com categoria/cor/tamanho/frete separados, descoberta aberta de fontes, não relaxamento de filtros e ordenação sem falso total.

O compartimento reserve tem política v1.0.0 e custódia humana de Pedro fora do repositório; foi definido, mas ainda não populado. Nenhum caso privado ou oferta real foi publicado. Itens e lojas dos fixtures são inventados.

O verificador aplica os filtros sintéticos e confere o estado esperado, mas não consulta lojas, navega, abre fontes, mede relevância em ambiente real ou executa MCP. A existência dos casos não demonstra qualidade de busca nem cobertura de sites.

## Execução

Na raiz do repositório, execute scripts/validate_eval_cases.py com CPython 3.13.15. O programa valida versão, separação, cobertura de ferramentas, critérios e invariantes determinísticas aplicáveis. Um caso aprovado pelo validador de fixtures significa apenas que seus dados/rubricas são coerentes; não representa avaliação do agente, execução, baseline ou aceite humano.
