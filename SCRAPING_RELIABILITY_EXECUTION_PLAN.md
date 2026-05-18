# Scraping Reliability Execution Plan

## Objetivo

Aproximar a app do comportamento desejado:

- publicar resultados frescos o mais cedo possível quando a FPF já os expõe;
- refletir alterações de data, hora e local antes dos jogos;
- distinguir claramente falha técnica, atraso normal da FPF e problema de parser;
- tornar os workflows "verdes" significativos do ponto de vista do utilizador.

Este plano parte do relatório `2-relatorio_analise_scores_cfa_estado_atual.txt` e adapta-o ao estado real do repositório.

## Avaliação do relatório

## Pontos com que concordo

- o problema principal já não é falta de automação; é falta de granularidade e observabilidade;
- `partial` está demasiado genérico para guiar operação e produto;
- `calendar_watch` e `result_chase` devem ser tratados como fluxos diferentes;
- o sistema precisa de memória técnica persistente entre runs;
- `run_fetchers.py` não deve inferir estados operacionais a partir de `stdout`;
- os commits automáticos podem dar sensação de frescura sem atualização real dos JSON de competição;
- o frontend deve depender dos JSON publicados, não de scraping no browser;
- `seniores.json` deve ser alinhado com o schema comum.

## Pontos que ajustaria

### Cache busting

Não usaria `?v=${Date.now()}` em produção como estratégia principal.

Preferência:

- `data/manifest.json` com `buildId` e `hash` por ficheiro;
- frontend a carregar JSON com `?v=<buildId>`;
- `cache: 'no-store'` apenas quando fizer sentido.

### Parsing

Concordo com a migração progressiva para parser DOM, mas não faria "big bang".

Preferência:

1. preservar parser atual;
2. introduzir parser DOM primeiro em `parse_matches`;
3. depois `parse_classification`;
4. só remover regex quando houver cobertura de testes suficiente.

### Cadência de resultados

Concordo que `kickoff + 2h` é conservador demais.

Preferência:

- começar a primeira verificação de score em `kickoff + 105/110 min`;
- manter retries de `15 min`;
- passar depois a `30 min`, não diretamente a `1h`.

## Diagnóstico operacional atual

Hoje o problema observado no repositório é este:

1. os workflows correm e publicam;
2. `calendar.json` e `status.json` são frequentemente regenerados;
3. vários `data/<competição>.json` ficam com `lastUpdatedAt` antigo;
4. o utilizador vê app stale apesar de workflows verdes.

Isto indica que o sistema precisa de distinguir:

- "workflow correu";
- "FPF respondeu";
- "dados mudaram";
- "JSON da competição mudou";
- "site publicou essa mudança".

Sem essa cadeia explícita, a operação parece saudável sem entregar valor ao utilizador.

## Estado de execução atual

### Blocos já concluídos

- Fase 1 / Bloco A — Observabilidade técnica
- Fase 2 / Bloco B — Relatório estruturado por fixture
- Fase 3 / Bloco C — Uniformização do schema publicado
- Fase 4 / Bloco D — Separação real de `calendar_watch` e `result_chase`

### Blocos ainda pendentes

- Bloco E — Planner com memória técnica
- Bloco F — Gates reais nos workflows
- Bloco G — Frontend e transparência
- Bloco H — Robustez do parser
- Bloco I — Testes operacionais

### Investigação dirigida em curso

Antes de avançar para o Bloco E, há uma investigação operacional obrigatória em dois casos de referência:

- `seniores`
- `infantis-b`

O que já ficou provado:

1. o Pages está a servir JSON stale nestas duas competições;
2. a FPF já tem dados mais frescos;
3. os fetchers locais conseguem gerar JSON novo;
4. em pelo menos um `Sync data` verde real, os fetchers foram executados mas classificados como `unchanged`;
5. o commit automático desse run alterou agregados, não os JSON dessas competições.

Isto desloca o foco atual para:

- deteção de mudança útil;
- persistência do round atualizado;
- decisão de commit/publicação;

e afasta, para estes casos:

- frontend;
- deploy do Pages;
- impossibilidade de acesso HTTP;
- incapacidade base do parser nessas duas competições.

## Checkpoint obrigatório antes do Bloco E

O sistema deve conseguir responder, para `seniores` e `infantis-b`, a estas perguntas sem ambiguidade:

1. a origem mudou?
2. o fetch correu?
3. o parser detetou a mudança?
4. o JSON final da competição mudou?
5. o Pages publicou essa mudança?

Enquanto esta cadeia não estiver fechada, avançar para o Bloco E só tornaria mais sofisticado um processo que ainda não garante publicação útil.

## Princípios de arquitetura

1. `data/<competição>.json` continua a ser a fonte principal da app.
2. `calendar.json` e `status.json` são derivados; nunca devem mascarar falta de atualização real das competições.
3. scraping no browser deve ser removido ou isolado em modo de diagnóstico.
4. cada fetch deve devolver resultado estruturado, não apenas HTML/`None`.
5. cada competição deve ter memória técnica persistente entre runs.
6. calendário futuro e resultados pós-jogo devem ter cadências distintas.
7. o workflow principal deve falhar em erros críticos reais antes de commit/deploy.

## Estado alvo

Para cada competição, o sistema deve saber:

- quando tentou;
- quando teve resposta útil;
- quando os dados mudaram;
- se falhou;
- por que falhou;
- que jornadas/fixtures foram afetados;
- se a mudança foi de:
  - score;
  - data;
  - hora;
  - estádio;
  - estrutura da jornada.

## Fase 1 — Observabilidade Técnica

### Objetivo

Parar de tratar fetch como "sucesso/falha" opaco.

### Entregáveis

1. `FetchResult` estruturado em `fpf_http.py`
2. `cache/fetch_state.json`
3. relatório por competição e por fixture
4. captura automática de HTML de erro

### Mudanças

- `fpf_http.py` passa a devolver estrutura com:
  - `ok`
  - `content`
  - `status_code`
  - `error_type`
  - `blocked`
  - `attempts`
  - `duration_seconds`
  - `response_size`
  - `url`
- criar `cache/fetch_state.json` com:
  - `lastAttemptAt`
  - `lastSuccessAt`
  - `lastChangedAt`
  - `lastErrorAt`
  - `lastErrorType`
  - `consecutiveFailures`
  - `technicalBackoffUntil`
- guardar HTML bruto em:
  - `cache/errors/<competition>/main_<timestamp>.html`
  - `cache/errors/<competition>/fixture_<fixtureId>_<timestamp>.html`

### Critérios de aceitação

- cada falha passa a ter `error_type` explícito;
- conseguimos responder objetivamente:
  - foi `403`?
  - foi `429`?
  - foi timeout?
  - foi parser?
  - foi bloqueio com HTML de segurança?

## Fase 2 — Relatório Estruturado de Mudança

### Objetivo

Saber o que realmente mudou em cada run.

### Entregáveis

1. relatório por fixture
2. deteção de mudança por campo
3. `run_fetchers.py` deixa de depender de `stdout`

### Mudanças

- `competition_sync.py` passa a produzir sidecar/metadata com:
  - `successfulFixtureIds`
  - `failedFixtureIds`
  - `reusedFixtureIds`
  - `calendarChangedCount`
  - `scoreChangedCount`
  - `technicalErrors`
- por fixture:
  - `fetchStatus`
  - `changed`
  - `changedFields`
  - `matchChanges`
  - `fallbackUsed`
  - `errorType`
- `run_fetchers.py` lê metadata estruturada em vez de procurar frases em `stdout`

### Critérios de aceitação

- um run deixa de ser "verde" sem significado;
- conseguimos ver se uma competição foi apenas verificada ou se mudou mesmo.

## Fase 3 — Uniformização do Schema Publicado

### Objetivo

Eliminar inconsistências entre competições.

### Entregáveis

1. schema comum obrigatório
2. `seniores.json` alinhado

### Campos mínimos por competição

- `schemaVersion`
- `generatedAt`
- `lastAttemptAt`
- `lastSuccessAt`
- `lastChangedAt`
- `lastPublishedAt`
- `sourceHealth`
- `dataQuality`
- `rounds`

### Campos mínimos por round

- `index`
- `fixtureId`
- `lastAttemptAt`
- `lastSuccessAt`
- `lastChangedAt`
- `sourceStatus`
- `sourceIssue`

### Campos mínimos por match

- `home`
- `away`
- `date`
- `time`
- `stadium`
- `homeScore`
- `awayScore`
- `scoreSource`
- `calendarSource`
- `lastChangedAt`
- `changeFlags`

### Critérios de aceitação

- todas as competições publicam o mesmo schema;
- `build_status.py` deixa de depender de exceções por competição.

## Fase 4 — Separação Real de Calendar Watch e Result Chase

### Objetivo

Tratar alterações de calendário futuro como problema independente dos resultados.

### Estados alvo

- `calendar_watch_far`
- `calendar_watch_near`
- `calendar_watch_matchday`
- `result_chase`
- `recent_historical_backfill`
- `historical_backfill`
- `technical_backoff`
- `idle`

### Cadência recomendada

#### Calendário

- `T-14d` a `T-8d`: `1x/dia`
- `T-7d` a `T-4d`: `12h`
- `T-3d` a `T-2d`: `6h`
- `T-24h` a kickoff: `1h` ou `2h`

#### Resultados

- `kickoff + 105/110 min`: primeira verificação
- depois `15 min` por 4 vagas
- depois `30 min` até `4h` ou `6h` pós-jogo
- depois `2h` durante `48h`
- depois `6h` até `14 dias`

### Critérios de aceitação

- uma alteração de horário na FPF passa a ter probabilidade alta de entrar na app antes do jogo;
- a atualização de resultados deixa de depender da mesma cadência usada para agenda futura.

## Fase 5 — Planner com Memória Técnica

### Objetivo

Decidir próxima tentativa com base em histórico real e não apenas no estado do JSON atual.

### Mudanças

- `plan_fetchers.py` passa a usar `fetch_state.json`
- aplicar backoff técnico por competição e, quando útil, por fixture
- distinguir:
  - `http_403`
  - `http_429`
  - `timeout`
  - `network_error`
  - `blocked_content`
  - `parse_error`
  - `no_fixture_ids`
  - `no_matches`

### Critérios de aceitação

- uma competição bloqueada não puxa o resto do sistema para um ciclo inútil;
- o planner deixa de repetir vagas cegas quando não há perspetiva de progresso.

## Fase 6 — Workflow Gates Reais

### Objetivo

Fazer o estado verde/vermelho do workflow refletir a utilidade do run.

### Mudanças

- mover validação crítica para antes do commit/deploy
- remover `continue-on-error` nos erros verdadeiramente críticos
- manter `warning` para `partial` normais

### Falhas críticas

- JSON inválido
- zero jornadas
- zero jogos
- perda anormal de jornadas/jogos
- competição esperada sem equipa do clube
- série/fase errada com baixa confiança

### Critérios de aceitação

- um run não faz commit de dados estruturalmente inúteis;
- um run verde significa pelo menos "dados verificados com validade aceitável".

## Fase 7 — Frontend e Transparência

### Objetivo

Mostrar ao utilizador o estado real dos dados.

### Mudanças

- criar `data/manifest.json` para cache busting controlado
- remover ou isolar scraping remoto morto em:
  - `main.js`
  - `agenda.js`
- mostrar:
  - `lastAttemptAt`
  - `lastSuccessAt`
  - `lastChangedAt`
  - `lastErrorType` quando relevante

### Mensagens alvo

- "Dados publicados atualizados em..."
- "Última tentativa de sincronização..."
- "Última alteração detetada..."
- "A FPF ainda não publicou X resultado(s)."
- "A FPF alterou data/hora deste jogo recentemente."
- "Estás a ver dados locais porque o JSON publicado não pôde ser carregado."

### Critérios de aceitação

- o utilizador percebe diferença entre:
  - dados verificados;
  - dados alterados;
  - dados pendentes;
  - falha técnica.

## Fase 8 — Robustez do Parser

### Objetivo

Reduzir fragilidade perante alterações HTML da FPF.

### Mudanças

- migrar `parse_matches` para parser DOM
- migrar `parse_classification` para parser DOM
- reforçar seleção de série/fase com:
  - aliases
  - confiança
  - validação por equipas esperadas
  - `target_serie_id` sempre que possível

### Critérios de aceitação

- pequenas alterações de HTML deixam de partir o scraping;
- `allow_first_block_fallback` passa a ser raro e explicitamente sinalizado.

## Fase 9 — Testes de Regressão Reais

### Objetivo

Proteger o sistema contra regressões operacionais, não apenas estruturais.

### Cobertura nova

- `403`
- `429`
- `timeout`
- `blocked_content`
- HTML sem classificação
- HTML alterado
- fixture com horário alterado mas score igual
- fixture reaproveitado
- série errada
- jogo adiado / `a indicar`

### Critérios de aceitação

- alterações em parser ou planner não degradam o comportamento sem aviso.

## Ordem recomendada de implementação

### Bloco A — primeiro

1. `FetchResult`
2. `fetch_state.json`
3. relatório por fixture
4. HTML de erro
5. schema uniforme

### Bloco B — segundo

6. separar `calendar_watch` de `result_chase`
7. cadência nova de calendário
8. primeira tentativa de score em `+105/110 min`
9. planner com memória técnica

### Bloco C — terceiro

10. workflow gates reais
11. `manifest.json`
12. remoção/isolamento do scraping remoto no browser
13. mensagens de estado ao utilizador

### Bloco D — quarto

14. parser DOM
15. reforço de série/fase
16. expansão de testes

## Resultado esperado

No fim deste plano, o sistema deve aproximar-se disto:

- rápido quando há jogo;
- agressivo apenas nas janelas úteis;
- conservador quando a FPF bloqueia;
- claro ao utilizador sobre o estado real dos dados;
- fácil de depurar quando a FPF muda HTML, horário ou resultado.

## Próximo passo recomendado

Antes de qualquer refactor grande, o primeiro bloco a executar deve ser:

1. `FetchResult`
2. `fetch_state.json`
3. relatório por fixture

Sem isso, continuaremos a mexer em cadências e workflows com pouca visibilidade sobre o que realmente falha.
