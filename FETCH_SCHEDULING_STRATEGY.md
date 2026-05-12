# Fetch Scheduling Strategy

## Status

This document is still useful as the high-level scheduling rationale.

However, part of the strategy has now been implemented more concretely in:

- [ADAPTIVE_FETCH_WINDOW_PLAN.md](/Users/mariocabano/Documents/GitHub/scores_CFA/ADAPTIVE_FETCH_WINDOW_PLAN.md)
- `plan_fetchers.py`
- `.github/workflows/retry-pending-results.yml`

The current code already supports:

- fetch timing based on match windows
- `kickoff + 2h` first meaningful fetch
- `15-minute` short chase for same-day pending scores
- hourly same-day continuation
- `2-hour` recent historical backfill
- `6-hour` historical recovery
- workflow follow-up based on `nextRecommendedFetchAt`
- lightweight initial sync wave, with heavier persistence deferred to follow-up

## Objetivo

Reduzir ao mínimo o scraping à FPF, sem perder resultados relevantes nem deixar competições estagnadas quando a origem atualiza tarde.

O princípio central é simples:

- não fazer polling cego por relógio;
- fazer scraping apenas quando existe motivo objetivo;
- aumentar a frequência apenas nas janelas em que há valor real;
- manter uma política específica para jogos antigos ainda sem resultado.

## Problema atual

O modelo baseado só em cron tem três limitações:

1. consulta a FPF mesmo em dias sem jogos;
2. continua a consultar competições cujos jogos do dia já estão todos fechados;
3. não distingue adequadamente:
   - jogos de hoje ainda por apurar;
   - jogos antigos que a FPF publicou tarde;
   - competições já totalmente estabilizadas.

Este padrão aumenta:

- o número de requests desnecessários;
- a probabilidade de bloqueio/403;
- o ruído operacional;
- a dificuldade de perceber quando um fetch é realmente necessário.

## Estratégia proposta

O scheduler deve passar a ser orientado por estado.

Em vez de perguntar:

- "já passou mais 30 ou 60 minutos?"

deve perguntar:

- "há algum jogo que justifique novo fetch?"

## Fonte de verdade para decidir

Antes de decidir se faz fetch, o sistema deve consultar os dados já publicados/localmente:

- `data/calendar.json`
- ou, se necessário, os `data/*.json` por competição

Com isso consegue saber:

- que jogos existem em cada data;
- que competições têm jogos hoje;
- que jogos já têm resultado;
- que jogos passados continuam sem score.

## Estados operacionais

### 1. `IDLE`

Situação:

- não há jogos hoje;
- não há jogos antigos pendentes dentro da janela de recuperação.

Comportamento:

- não correr fetch competitivo;
- opcionalmente correr apenas um health-check técnico muito leve.

### 2. `PRE_MATCH`

Situação:

- existem jogos hoje, mas ainda antes da hora útil de monitorização.

Comportamento:

- no máximo uma verificação leve;
- evitar polling repetido cedo demais.

Exemplo:

- jogo às `16:00`
- não faz sentido fazer polling agressivo às `09:00`

### 3. `LIVE_WINDOW`

Situação:

- há jogos de hoje que já começaram, já deviam ter terminado, ou ainda não têm resultado publicado.

Comportamento:

- ativar polling mais frequente;
- exemplo:
  - ciclo base de `60 em 60 minutos`
  - retries adicionais de `5 em 5` ou `10 em 10` apenas para competições pendentes

### 4. `CLOSED_TODAY`

Situação:

- todos os jogos de hoje já têm resultado.

Comportamento:

- parar polling desse dia;
- não voltar a consultar essas competições apenas por relógio.

### 5. `BACKFILL_PENDING`

Situação:

- não há pendências hoje;
- mas existem jogos de dias anteriores sem resultado.

Comportamento:

- ativar um ciclo de recuperação mais leve, separado do ciclo de hoje;
- o objetivo aqui não é polling agressivo, mas revalidação periódica e económica.

Este estado é obrigatório para cobrir o caso:

- hoje é dia `10`
- todos os jogos do dia `10` já estão fechados
- mas existe um jogo do dia `2` que a FPF só publica mais tarde

Sem este estado, o sistema deixaria de tentar recuperar esse resultado antigo.

## Caso crítico: jogo antigo ainda sem resultado

Este caso deve ser tratado explicitamente.

Exemplo:

- estamos no dia `10`
- os jogos do dia `10` estão todos fechados
- existe um jogo do dia `2` ainda sem score

### Como lidar

O scheduler não deve assumir que "dia fechado" significa "competição fechada".

Deve existir uma noção separada de:

- `pendências do dia atual`
- `pendências históricas`

### Regra recomendada

Para jogos passados sem resultado, criar uma **janela de recuperação histórica**.

Exemplo:

- considerar jogos sem score dos últimos `14 dias`
- ou `21 dias`, consoante o comportamento típico da FPF

Dentro dessa janela:

- esses jogos continuam elegíveis para fetch;
- mas com frequência menor do que os jogos do dia.

### Política sugerida

- jogos de hoje pendentes:
  - polling mais agressivo
- jogos de 1 a 3 dias atrás pendentes:
  - polling moderado
- jogos de 4 a 14 dias atrás pendentes:
  - polling leve
- jogos além dessa janela:
  - marcar para revisão manual ou health-check diário

Isto evita duas coisas:

1. desistir cedo demais de resultados atrasados;
2. ficar eternamente a consultar jogos muito antigos sem probabilidade real de mudança.

## Modelo de frequência recomendado

### Ciclo base

- `1x por hora`

### Se houver jogos de hoje pendentes

- repetir `1x por hora`
- se o fetch falhar ou vier degradado:
  - retries curtos
  - por exemplo `+10 min`, `+20 min`, `+30 min`

### Se só houver pendências históricas

- usar ritmo muito mais leve
- por exemplo:
  - `2x por dia`
  - ou `1x por dia`, dependendo da antiguidade

## Seleção do que deve ser consultado

O sistema não deve fazer fetch a todas as competições sempre.

Deve primeiro construir uma lista de competições ativas:

- competições com jogos hoje sem resultado;
- competições com jogos históricos pendentes dentro da janela de recuperação.

Todas as restantes devem ser ignoradas nessa execução.

## Granularidade ideal

A decisão deve ser tomada por competição e, idealmente, por `fixtureId`.

Isto permite:

- não reconsultar jornadas inteiras sem necessidade;
- insistir apenas nos blocos realmente pendentes.

## Benefícios esperados

1. Menos requests à FPF
2. Menos probabilidade de 403 / rate-limiting
3. Menos runs inúteis do GitHub Actions
4. Menos regressões de dados
5. Melhor foco nas competições realmente pendentes
6. Melhor capacidade de recuperar resultados atrasados

## Riscos e cuidados

### 1. Horários inexatos

A hora do jogo publicada pode não ser suficientemente fiável.

Mitigação:

- usar margem de tolerância;
- por exemplo ativar `LIVE_WINDOW` não exatamente na hora do jogo, mas numa janela como:
  - `-30 min` até `+4 h`

### 2. Resultados parciais

A FPF pode atualizar alguns jogos e outros não.

Mitigação:

- a decisão deve ser por jogo/jornada, não apenas por competição global.

### 3. Jogos antigos eternamente pendentes

Mitigação:

- impor janela histórica finita;
- acima desse limite, reduzir para verificação muito leve ou revisão manual.

## Recomendação de implementação

### Fase 1

## Próximos passos imediatos

1. publicar a implementação atual
2. observar 1 ou 2 ciclos reais do workflow
3. se fizer sentido, refinar a classificação técnica de erro em `run_fetchers.py`:
   - `403`
   - `429`
   - `timeout`
   - `network_error`

Adicionar um avaliador de necessidade de fetch:

- lê `calendar.json`
- identifica jogos de hoje pendentes
- identifica jogos históricos pendentes
- devolve o plano de execução

### Fase 2

Separar frequências:

- hoje pendente -> polling forte
- histórico pendente -> polling leve
- sem pendências -> não fazer fetch competitivo

### Fase 3

Fazer o workflow agir com base nesse plano:

- correr apenas os fetchers necessários
- ou não correr nenhum scraper competitivo se não houver motivo

## Critérios de aceitação

1. Em dias sem jogos e sem pendências históricas, o sistema não faz scraping competitivo.
2. Em dias com jogos todos fechados, o sistema deixa de insistir desnecessariamente.
3. Jogos antigos ainda sem resultado continuam a ser revalidados dentro da janela histórica.
4. Competições sem qualquer pendência deixam de ser consultadas por rotina.
5. O número total de requests à FPF desce sem perda de cobertura útil.

## Conclusão

Esta abordagem é melhor do que um cron fixo puro.

Transforma o workflow em algo:

- mais económico;
- mais resiliente;
- mais orientado a valor;
- e mais compatível com a instabilidade da FPF.

O ponto crítico fica contemplado:

- mesmo que o dia atual esteja totalmente fechado, um jogo antigo ainda sem resultado continua a poder justificar fetch, mas num modo de recuperação histórica, não num modo agressivo.
