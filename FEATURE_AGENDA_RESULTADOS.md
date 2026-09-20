# Agenda E Resultados Globais

## Estado Atual

A Agenda é construída diretamente no browser a partir das competições ativas em `data/competitions/index.json`. Não existe ficheiro agregado intermédio.

## Comportamento

- `Próximos Jogos` mostra jogos do clube ainda sem resultado;
- `Resultados` mostra jogos com os dois scores preenchidos;
- ambos aceitam intervalo de datas e filtro por competição;
- os jogos são agrupados por dia;
- próximos jogos usam ordem cronológica ascendente;
- resultados usam ordem cronológica descendente;
- cada cartão liga à jornada correspondente na página da competição.

## Identificação Da Equipa

A Agenda só inclui um jogo quando a equipa da casa ou visitante coincide com um dos valores `teamNames` da respetiva entrada no catálogo. Isto permite distinguir, por exemplo, equipa principal, equipa A e equipa B.

## Dados Apresentados

- competição e série/fase;
- jornada;
- equipas e emblemas;
- hora ou resultado;
- data e recinto.

## Filtros

O período é selecionado num calendário modal. O filtro de competição é preenchido dinamicamente pelo catálogo. Não existem atalhos fixos como `Hoje` ou `Próximos 7 dias`.

## Atualização

Substituir um JSON de competição é suficiente. No carregamento seguinte, a Agenda passa a usar os novos jogos, datas, horas e resultados; não há nenhum build agregado a executar.

## Critérios De Integridade

- o catálogo deve apontar para um ficheiro existente;
- o ficheiro deve conter `rounds`;
- `validation.complete` não pode ser `false`;
- os jogos devem fornecer `date`, `home` e `away` para ordenação e identificação fiáveis;
- `teamNames` deve reproduzir o nome usado no JSON.
