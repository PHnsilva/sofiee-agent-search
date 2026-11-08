# Contrato da ferramenta de Busca v1

`contracts.json` define um contrato JSON Schema Draft 2020-12 para `search.query`, versão `1.0.0`. O contrato deixa `sourceHints` e fontes abertas, sem whitelist global, e representa cada filtro, ordenação pedida, paginação e estado de verificação no resultado.

Filtros obrigatórios são uma interseção. A fixture sintética “camisa branca tamanho M” representa categoria e cor como filtros separados; tamanho e frete também não podem ser descartados silenciosamente. Itens com filtro reprovado não são resultados elegíveis. Itens com requisito não verificável precisam aparecer como não verificados. A ordenação só pode ser marcada como aplicada com uma base declarada; se valores necessários como frete faltarem, o resultado registra `not_comparable` e o motivo.

`scripts/validate_contracts.py` confere as fixtures e algumas invariantes de domínio com a biblioteca padrão do Python. Não é validador completo de JSON Schema nem prova a execução de uma busca. O runtime deverá validar o schema com o SDK definido para o agente, consultar fontes e manter evidência atual por resultado. Não há runtime, acesso a fontes, coleta de credenciais ou integração MCP neste incremento.

Execute `C:/SDKs/Python313/python.exe scripts/validate_contracts.py` a partir da raiz do repositório. As referências `fixture://` são dados sintéticos e não descrevem uma oferta real.
