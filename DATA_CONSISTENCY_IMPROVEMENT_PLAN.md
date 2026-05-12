# Data Consistency Improvement Plan

## Objetivo

Garantir que resultados, jornadas, classificações e agenda são publicados de forma consistente e consumidos da mesma forma por todos os dispositivos.

Arquitetura alvo:

`FPF -> sincronização/validação -> JSON publicados em data/ -> app`

Arquitetura a evitar:

`browser -> FPF -> dados por dispositivo`

## Avaliação do relatório recebido

O relatório está globalmente alinhado com os problemas reais do projeto:

- falhas silenciosas no scraper;
- divergência entre dispositivos;
- workflow demasiado tolerante a dados maus;
- falta de estado global por competição;
- necessidade de agenda e páginas usarem a mesma fonte de verdade.

Há, no entanto, dois ajustes importantes:

1. Não usar `?v=${Date.now()}` como estratégia principal de cache busting.
   - Isso destrói cache útil.
   - Aumenta tráfego.
   - Não resolve a qualidade do JSON publicado.
   - A solução correta é: JSON publicado como fonte autoritativa, metadata explícita e `localStorage` apenas como fallback.

2. Parte do plano já está parcialmente implementada.
   - scheduler adaptativo;
   - retries curtos;
   - agenda baseada nos JSON finais;
   - remoção da hidratação runtime como fonte principal;
   - deploy inicial separado dos retries.

Este documento adapta o plano ao estado atual do repositório.

## Estado atual resumido

Já existe:

- motor comum de sincronização em `competition_sync.py`;
- configuração central em `competition_configs.py`;
- workflow com planeamento adaptativo;
- deploy do site separado da sincronização de dados;
- deploy de `data/*.json` garantido mesmo em commits manuais;
- vaga inicial leve no `Sync data`, com insistência deixada para o follow-up;
- follow-up separado do workflow principal;
- agenda construída a partir dos JSON finais;
- `sourceHealth` e `lastUpdatedAt` nos payloads;
- `status.json` global;
- frontend mais dependente de JSON publicado do que de hidratação local.
- planner temporal com `nextRecommendedFetchAt`;
- follow-up workflow orientado a janela temporal em vez de vagas fixas cegas.
- tier `recent_historical_backfill` para resultados históricos muito recentes.

Ainda falta consolidar:

- falha explícita em erros críticos de scraping;
- política forte de validade mínima por competição;
- UX mais clara para estados `degraded`, `partial` e `local cache fallback`;
- diagnóstico centralizado por competição;
- logs estruturados por competição quando a FPF falha.

## Princípios de implementação

1. O JSON publicado é a fonte de verdade.
2. O browser nunca deve “inventar” um estado melhor que o publicado.
3. `localStorage` só serve como fallback curto quando o fetch do JSON falha.
4. Dados degradados podem ser publicados, mas nunca silenciosamente.
5. Dados estruturalmente inválidos não devem ser publicados.
6. A agenda deve derivar sempre dos JSON finais das competições.

## Fase 1 — Endurecer a sincronização

### Objetivo

Impedir sucesso silencioso quando a extração falha ou devolve dados estruturalmente fracos.

### Alterações

- endurecer `competition_sync.py` para distinguir:
  - erro crítico;
  - degradação aceitável;
  - sucesso real.
- falhar explicitamente quando:
  - não há página principal válida;
  - não há `fixtureId` válido;
  - não há jornadas;
  - não há jogos;
  - não há equipas;
  - o payload final fica estruturalmente inválido.
- manter modo `degraded` apenas quando:
  - existem dados mínimos válidos;
  - mas parte das jornadas precisou de reaproveitamento/fallback.

### Critérios de aceitação

- um scraper sem dados mínimos válidos termina com erro;
- um scraper degradado gera JSON válido com `sourceHealth` explícito;
- deixa de existir “success” sem dados utilizáveis.

## Fase 2 — Definir política mínima de qualidade por competição

### Objetivo

Evitar publicar JSON “tecnicamente válidos” mas demasiado incompletos.

### Alterações

- criar validação comum com métricas por competição:
  - `roundCount`
  - `matchCount`
  - `teamCount`
  - `matchesWithoutScore`
  - `fallbackReuseCount`
  - `updatedRoundsCount`
- definir limiares:
  - crítico: sem jornadas, sem jogos, sem equipas;
  - degradado: jornadas reaproveitadas, alguns resultados ainda ausentes;
  - parcial: estrutura válida mas com lacunas recentes.

### Critérios de aceitação

- cada fetch termina classificado como `ok`, `partial`, `degraded` ou `critical_error`;
- a classificação é consistente entre competições.

## Fase 3 — Criar `data/status.json`

### Objetivo

Ter um ficheiro global com o estado de todas as competições.

### Estrutura proposta

```json
{
  "generatedAt": "2026-05-10T21:11:55Z",
  "competitions": {
    "seniores": {
      "status": "ok",
      "lastUpdatedAt": "2026-05-10T21:11:55Z",
      "fallbackReuseCount": 0,
      "matchesWithoutScore": 0,
      "updatedRoundsCount": 3
    }
  }
}
```

### Utilização

- homepage;
- seletor de competições;
- páginas de competição;
- agenda;
- futura página admin;
- diagnóstico rápido do workflow.

### Critérios de aceitação

- a app consegue conhecer o estado global sem abrir todos os `data/*.json`;
- o workflow publica `status.json` em todas as sincronizações.

## Fase 4 — Frontend estritamente orientado a JSON publicado

### Objetivo

Reduzir ainda mais a divergência entre dispositivos.

### Alterações

- manter `data/<competição>.json` e `data/calendar.json` como fonte autoritativa;
- manter `localStorage` apenas como fallback quando o fetch falha;
- mostrar aviso claro quando:
  - foi usado fallback local;
  - os dados estão `degraded`;
  - os dados estão `partial`.

### Nota de implementação

Não usar `Date.now()` em todos os `fetch()` como política base.

Preferir:

- metadata de atualização (`lastUpdatedAt`);
- `status.json`;
- cache-control coerente no Pages/CDN;
- fallback local só em caso de erro real de rede.

### Critérios de aceitação

- dois dispositivos com internet convergem para o mesmo JSON publicado;
- o utilizador percebe quando está a ver fallback local.

## Fase 5 — Reforçar workflow e política de publicação

### Objetivo

Publicar cedo o que for válido, sem esconder falhas críticas.

### Alterações

- manter:
  - deploy inicial rápido;
  - follow-up de retries em workflow separado;
- reforçar:
  - falha do workflow em erros críticos;
  - visibilidade de `partial` e `degraded`;
  - resumo por competição no GitHub Actions;
- publicar sempre:
  - `data/*.json`
  - `data/calendar.json`
  - `data/status.json`

### Critérios de aceitação

- o workflow principal fecha rapidamente;
- retries não bloqueiam o primeiro deploy;
- falhas críticas são visíveis;
- dados válidos são publicados mesmo com degradação parcial noutras competições.

## Fase 6 — Melhorar a lógica de atualização por calendário

### Objetivo

Concentrar esforço de scraping nas competições com maior probabilidade de mudança.

### Regras alvo

- jogos de hoje: prioridade máxima;
- jogos de ontem: prioridade alta;
- últimos 7 dias com resultados em falta: revisão leve;
- jogos antigos sem score: backfill controlado, não insistência contínua.

### Nota

Parte desta fase já existe em `plan_fetchers.py`.

Neste momento já existe:

- separação entre `awaiting_window`, `result_chase` e `historical_backfill`;
- primeira tentativa útil em `hora do jogo + 2h`;
- follow-up guiado por `nextRecommendedFetchAt`;
- recuperação histórica em janela mais lenta.

O que ainda falta consolidar:

- classificação técnica explícita de erros;
- persistência de memória técnica entre runs;
- tuning do planeador com base em runs reais.

### Critérios de aceitação

- menos fetches inúteis;
- mais tentativas onde há probabilidade real de novos resultados.

## Fase 7 — Diagnóstico/Admin

### Objetivo

Diagnosticar rapidamente discrepâncias sem abrir ficheiros manualmente.

### Entregável

Uma página `admin.html` ou equivalente com:

- última geração;
- estado por competição;
- jornadas;
- jogos;
- jogos sem score;
- fallback reuse;
- último erro;
- origem FPF;

## Próximos passos imediatos

1. publicar a implementação atual do `ADAPTIVE_FETCH_WINDOW_PLAN`
2. observar 1 ou 2 ciclos reais do workflow
3. se fizer sentido, refinar a classificação técnica de erro em `run_fetchers.py`:
   - `403`
   - `429`
   - `timeout`
   - `network_error`
- indicação se a app está a consumir JSON publicado ou fallback local.

### Critérios de aceitação

- identificar rapidamente o motivo de uma competição estar desatualizada.

## Ordem recomendada

### Bloco crítico

1. Endurecer `competition_sync.py`
2. Definir política mínima de qualidade
3. Criar `data/status.json`
4. Ajustar mensagens/estados no frontend
5. Reforçar política do workflow

### Bloco de consolidação

6. Consolidar scheduler por calendário
7. Criar modo admin/diagnóstico
8. Melhorar logs estruturados e captura de erro por competição

## Decisões explícitas

### Concordo com:

- eliminar dependência do browser para scraping;
- usar JSON publicado como fonte de verdade;
- distinguir erro crítico de degradação;
- criar estado global por competição;
- tornar a agenda e as páginas coerentes entre si.

### Não adotaria literalmente:

- cache busting com `Date.now()` em todos os `fetch()`;
- publicação silenciosa de qualquer payload estruturalmente fraco;
- dependência forte e duradoura de `localStorage`.

## Resultado esperado

Depois destas fases:

- todos os dispositivos leem a mesma fonte de verdade;
- o workflow deixa de aparentar sucesso com dados maus;
- competições degradadas continuam visíveis como degradadas;
- agenda e competição deixam de divergir;
- problemas tornam-se diagnosticáveis sem inspeção manual dos JSON.
