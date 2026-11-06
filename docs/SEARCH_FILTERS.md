# Busca: semântica, filtros e ordenação

Busca não tem whitelist global de fontes. Deve usar fontes pertinentes e respeitar as restrições pedidas em cada consulta. Quando Validação pede artigos ou fonte oficial, esse filtro vale para aquela consulta, não para toda atividade do Busca.

## Contrato do pedido

Representar assunto/categoria, atributos, operadores (igual, diferente, intervalo, inclusão/exclusão), critérios obrigatórios, preferências, fontes/região/idioma/período, ordenação e limites de cobertura. Se “bem avaliado” não vier com critério suficiente nem política explícita do consumidor, pedir esclarecimento; não inventar uma nota mínima e chamá-la de exigência do usuário.

## Semântica que não pode se perder

“Camisa branca” exige camisa **e** branca. Uma camisa azul e um sapato branco não atendem. “Camisa branca tamanho M, nota do produto ≥4,5/5 com pelo menos 20 avaliações, menor preço total entregue” exige todas essas condições, na variante efetivamente ofertada. Os números são exemplo de uma consulta explícita, não defaults universais.

Separar atributos obrigatórios de preferências. Não retirar cor/tamanho/avaliação quando houver poucos resultados. Retorno vazio ou atributo não verificável é um resultado válido; alternativas mais amplas só aparecem identificadas e quando permitidas pelo usuário.

## Estratégia por fonte

Descobrir capacidades e aplicar filtros nativos por API/conector ou pelos controles reais da navegação autorizada. Conferir que o filtro/ordenação foi aplicado. Como sites usam taxonomias diferentes, normalizar o significado antes de comparar e revalidar os resultados após a recuperação.

Mercado Livre e SHEIN são integrações iniciais, não o limite conceitual do agente. Outras lojas/fontes entram por adaptador com critérios e evidência; “qualquer lugar” não significa prometer suporte já implementado a todo site, contornar acesso ou realizar compras.

## Comparação e evidência

- Distinguir avaliação de produto e vendedor e quantidade de avaliações; dado ausente não passa no filtro de nota.
- Comparar a mesma variante e quantidade. Preço de parcela não é preço total; cupom condicional não é desconto garantido.
- Se o usuário pede preço total, incluir frete quando conhecido. Frete desconhecido não é zero; moeda/região e conversão precisam de método e instante.
- Ordenar após a pós-filtragem e deduplicar com cuidado. Se só parte das páginas/fontes foi consultada, declarar cobertura e não alegar o menor preço de toda a internet.
- Entregar URL/ID original, instante e trilha dos critérios, distinguindo extração, declaração da fonte e inferência. Validação poderá abrir e conferir novamente essas referências.
