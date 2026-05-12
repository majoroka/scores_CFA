# Feature Spec: Agenda E Resultados Globais

## Estado Atual

Esta feature já está implementada na base, mas o comportamento final divergiu em alguns pontos do plano original.

Hoje já existe:

- página dedicada em [agenda.html](/Users/mariocabano/Documents/GitHub/scores_CFA/agenda.html);
- script dedicado em [agenda.js](/Users/mariocabano/Documents/GitHub/scores_CFA/agenda.js);
- agregado publicado em [data/calendar.json](/Users/mariocabano/Documents/GitHub/scores_CFA/data/calendar.json);
- leitura `published-first`, alinhada com o resto da app;
- picker de período por calendário, em modal centrado;
- filtro por competição;
- cards visuais com badge de competição colorido e layout responsivo.

Já não faz parte da implementação atual:

- atalhos rápidos como `Hoje`, `Fim de semana`, `Próximos 7 dias`, `Últimos 7 dias`.

## Objetivo

Adicionar uma funcionalidade global de consulta transversal a todas as competições, permitindo:

1. consultar `próximos jogos` por intervalo de datas;
2. consultar `resultados` por intervalo de datas ou por competição.

O objetivo principal é deixar de obrigar o utilizador a entrar competição a competição para perceber:

- que jogos vão acontecer num dado período;
- que jogos já aconteceram e quais foram os resultados.

## Problema Atual

Hoje a app está organizada por competição. Isso funciona bem para consulta detalhada, mas não resolve bem estes casos:

- ver todos os jogos do clube num fim de semana;
- ver todos os resultados recentes sem abrir várias páginas;
- comparar rapidamente a agenda de várias equipas;
- encontrar jogos por data, e não apenas por competição.

## Proposta De Produto

Criar uma área global dedicada, acessível a partir da navegação principal.

Em vez de esconder isto num menu hamburger como primeira iteração, a proposta recomendada é:

- adicionar uma entrada visível no topo, por exemplo `Agenda`;
- dentro dessa página, apresentar duas tabs:
  - `Próximos Jogos`
  - `Resultados`

O hamburger pode ser reconsiderado mais tarde, mas não é a solução preferida para uma funcionalidade que deve ficar facilmente acessível.

## Casos De Uso

### 1. Próximos Jogos

O utilizador entra em `Agenda > Próximos Jogos` e pode:

- escolher um intervalo de datas, por exemplo `15 maio` a `16 maio`;
- ver todos os jogos de todas as competições nesse intervalo;
- ordenar por data e hora ascendente;
- perceber rapidamente:
  - equipa
  - adversário
  - competição
  - jornada
  - data/hora
  - estádio

### 2. Resultados

O utilizador entra em `Agenda > Resultados` e pode:

- escolher um intervalo de datas;
- ou escolher uma competição;
- ver todos os jogos disputados nesse período ou nessa competição;
- ordenar por data e hora descendente;
- perceber rapidamente:
  - resultado
  - competição
  - jornada
  - data
  - estádio

## Requisitos Funcionais

### Navegação

- Deve existir uma nova página dedicada, por exemplo `agenda.html`.
- A página deve ter duas tabs:
  - `Próximos Jogos`
  - `Resultados`

### Filtros

#### Próximos Jogos

- Filtro obrigatório por intervalo de datas.
- O período é escolhido exclusivamente através do calendário modal.
- A vista abre vazia até o utilizador aplicar um período.

#### Resultados

- Filtro por intervalo de datas.
- Filtro opcional por competição.
- O período é escolhido exclusivamente através do calendário modal.

### Ordenação

#### Próximos Jogos

- Ordem ascendente por data/hora.

#### Resultados

- Ordem descendente por data/hora.

### Agrupamento

Recomendado agrupar visualmente por dia:

- `Sábado, 16 maio`
- `Domingo, 17 maio`

Isto melhora bastante a leitura quando existem vários jogos em datas próximas.

### Dados a mostrar por jogo

Cada item da lista mostra:

- competição
- subtítulo da competição
- jornada
- equipa da casa
- equipa visitante
- data
- hora
- estádio
- resultado, quando aplicável

## Requisitos Técnicos

## Fonte De Dados

Não é recomendável construir esta funcionalidade agregando todos os `data/*.json` diretamente no browser.

Essa abordagem tem vários problemas:

- demasiadas requests;
- parsing duplicado no cliente;
- ordenação mais frágil;
- maior custo em mobile;
- maior risco de inconsistências.

### Abordagem Recomendada

Gerar no pipeline um ficheiro agregado global, por exemplo:

- `data/calendar.json`

Este ficheiro é produzido durante o processo de sync, a partir dos JSON de todas as competições.

## Estrutura De Dados Recomendada

Cada jogo agregado deve ser publicado num formato normalizado semelhante a este:

```json
{
  "competitionKey": "feminino-sub17",
  "competitionTitle": "Feminino - Sub17",
  "competitionSubtitle": "Liga 2 Algarve Futebol (2ª Fase - Série 7)",
  "roundNumber": 9,
  "fixtureId": "641038",
  "matchDateISO": "2026-05-03T11:00:00+01:00",
  "sortTimestamp": 1777792800,
  "status": "finished",
  "home": "Cf Os Armacenenses - A",
  "away": "Ud Messinense",
  "homeScore": 6,
  "awayScore": 0,
  "displayDate": "3 mai",
  "displayTime": "11:00",
  "stadium": "Estádio Municipal Armação De Pêra"
}
```

## Campos Adicionais Recomendados

Para a funcionalidade ficar robusta, o pipeline deve normalizar e publicar:

- `matchDateISO`
- `sortTimestamp`
- `status`
  - `scheduled`
  - `finished`
  - `postponed` (se vier a existir)
  - `unknown`
- `competitionKey`
- `competitionTitle`
- `competitionSubtitle`
- `roundNumber`

## Lógica De Classificação Dos Jogos

### Próximos Jogos

Entram na lista apenas jogos com:

- `status = scheduled`
- `matchDateISO` dentro do intervalo selecionado

### Resultados

Entram na lista apenas jogos com:

- `status = finished`
- `matchDateISO` dentro do intervalo selecionado

ou:

- `competitionKey` correspondente ao filtro escolhido

## Alterações Necessárias Na Arquitetura

### Pipeline

Será necessário acrescentar uma etapa ao pipeline atual:

1. correr todos os fetchers;
2. validar todos os JSON por competição;
3. gerar o ficheiro agregado global;
4. publicar esse ficheiro junto com os restantes `data/*.json`.

### Backend/Build

Recomendado criar um gerador dedicado, por exemplo:

- `build_calendar.py`

Responsabilidades:

- ler todos os `data/*.json` de competições;
- ignorar ficheiros não competitivos como `crests.json`;
- normalizar cada jogo;
- inferir `status`;
- gerar lista global ordenada;
- escrever `data/calendar.json`.

### Frontend

Criar uma nova página, por exemplo:

- `agenda.html`

e reutilizar `main.js` apenas se isso não complicar demasiado a separação de responsabilidades.

Implementado:

- [agenda.js](/Users/mariocabano/Documents/GitHub/scores_CFA/agenda.js) foi separado de [main.js](/Users/mariocabano/Documents/GitHub/scores_CFA/main.js)
- a Agenda consome `data/calendar.json`
- a página usa a mesma política `published-first` do resto da app

## Requisitos De Performance

- A página deve fazer idealmente apenas:
  - 1 request para `data/calendar.json`
  - 1 request para `data/crests.json`
- O filtro deve ser executado no cliente sobre dados já normalizados.
- A renderização deve ser imediata após carregamento do ficheiro agregado.

## Requisitos De UX

- Funcionar bem em desktop e mobile.
- Os filtros devem ser simples e explícitos.
- A listagem deve ser legível com muitos jogos.
- Deve ser evidente a que competição pertence cada jogo.
- Em mobile, a ordem de leitura recomendada é:
  - data/hora
  - equipas
  - resultado ou estado
  - competição
  - estádio

## Estado da UI

### Picker de período

- modal centrado no ecrã
- seleção apenas por calendário
- período inicial vazio até o utilizador confirmar

### Cards de jogo

- badge de competição com cor sólida por competição
- jornada e score/hora destacados
- layout com adaptações específicas para desktop e mobile

## Questões que esta feature já resolveu

- deixou de ser necessário abrir competição a competição para ver agenda global;
- eliminou dependência do browser para agregação local pesada;
- alinhou a Agenda com a mesma fonte de verdade publicada da app.

## Requisitos De Robustez

- O pipeline deve falhar se `calendar.json` for gerado vazio de forma incoerente.
- O gerador deve ignorar jogos com dados manifestamente inválidos, mas reportá-los.
- O processo deve ser determinístico: a mesma entrada deve produzir a mesma ordenação.
- A ordenação nunca deve depender apenas de strings visuais como `3 mai`.

## Fases De Implementação Recomendadas

### Fase 1

- Enriquecer os dados das competições com data normalizada por jogo.
- Publicar `matchDateISO`, `sortTimestamp` e `status`.

### Fase 2

- Criar gerador agregado `calendar.json`.
- Integrá-lo no workflow de atualização.

### Fase 3

- Criar `agenda.html`.
- Criar `agenda.js`.
- Implementar tabs `Próximos Jogos` e `Resultados`.

### Fase 4

- Refinar UX:
  - atalhos rápidos
  - agrupamento por dia
  - filtros por competição
  - eventual entrada via hamburger, se ainda fizer sentido

## Decisões Recomendadas

- `Sim` a uma página dedicada.
- `Sim` a um ficheiro agregado global.
- `Não` a depender de agregação no browser como solução principal.
- `Não` a usar menu hamburger como único ponto de acesso na primeira versão.

## Critérios De Aceitação

### Próximos Jogos

- Dado um intervalo de datas, a página lista todos os jogos agendados nesse intervalo.
- Os jogos aparecem ordenados por data/hora ascendente.
- Cada jogo mostra competição, jornada, equipas, data/hora e estádio.

### Resultados

- Dado um intervalo de datas, a página lista todos os jogos concluídos nesse intervalo.
- Dado um filtro de competição, a página lista todos os resultados dessa competição.
- Os jogos aparecem ordenados por data/hora descendente.

### Robustez

- A funcionalidade não depende de múltiplos fetches a todos os `data/*.json` no browser.
- A ordenação não depende de parsing frágil de strings visuais em runtime.
- A página continua funcional em mobile com boa performance.

## Próximo Passo Recomendado

O próximo passo natural é transformar esta especificação num plano técnico curto com:

- formato exato de `calendar.json`;
- alterações necessárias em [competition_sync.py](/Users/mariocabano/Documents/GitHub/scores_CFA/competition_sync.py);
- desenho de [agenda.html](/Users/mariocabano/Documents/GitHub/scores_CFA/agenda.html) e `agenda.js`.
