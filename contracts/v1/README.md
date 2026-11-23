# Contrato da ferramenta de Busca v1

`contracts.json` define um contrato JSON Schema Draft 2020-12 para `search.query`, versão `1.0.0`. O contrato deixa `sourceHints` e fontes abertas, sem whitelist global, e representa cada filtro, ordenação pedida, paginação e estado de verificação no resultado.

Filtros obrigatórios são uma interseção. A fixture sintética “camisa branca tamanho M” representa categoria e cor como filtros separados; requisitos não podem ser descartados silenciosamente. Itens com filtro reprovado não são resultados elegíveis. Itens com requisito não verificável precisam aparecer como não verificados. `sortAudit.requested` registra a sequência completa de campos e direções solicitada. `sortAudit.applied` registra o prefixo realmente aplicado, na mesma ordem. O estado `applied` exige a sequência completa e uma base; `partial` exige um prefixo incompleto e motivo; `not_comparable` não registra campos aplicados e explica a limitação. A fixture adicional cobre preço ascendente e avaliação descendente como desempate. Se valores necessários como frete faltarem, o resultado registra `not_comparable` e o motivo.

`scripts/validate_contracts.py` confere as fixtures e invariantes de domínio com a biblioteca padrão do Python. Não é validador completo de JSON Schema nem prova a execução de uma busca. Este incremento valida a representação do contrato e fixtures sintéticas; não executa busca em fontes nem demonstra ordenação aplicada por um provedor. O runtime é entregue separadamente.

Execute `C:/SDKs/Python313/python.exe scripts/validate_contracts.py` a partir da raiz do repositório. As referências `fixture://` são dados sintéticos e não descrevem uma oferta real.
