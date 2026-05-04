# Plano de Refatoração dos Fetchers e da Publicação de Dados

## Objetivo

Tornar a atualização de resultados e classificações mais robusta, previsível e uniforme entre competições, dispositivos e execuções automáticas.

O objetivo final é:

- obter dados frescos sempre que existam na origem;
- nunca degradar um JSON válido por causa de um fetch parcial ou bloqueado;
- abrir sempre cada competição na jornada correta para a data atual;
- reduzir a duplicação entre `fetch_*.py`;
- diminuir a dependência de lógica corretiva no browser.

## Problemas atuais

### 1. Dependência excessiva de scraping HTML

- A FPF responde por vezes com `403`, páginas de verificação ou HTML inconsistente.
- Um fetch pode funcionar para umas jornadas e falhar para outras na mesma execução.
- O scraping por regex é sensível a alterações pequenas no markup.

### 2. Múltiplos fetchers quase iguais

- Existem vários `fetch_*.py` com a mesma estrutura base.
- Pequenas correções têm de ser replicadas manualmente em muitos ficheiros.
- Isto aumenta a probabilidade de comportamentos divergentes entre competições.

### 3. Mistura entre dados publicados e hidratação no frontend

- O frontend carrega JSON local e depois tenta enriquecer com dados remotos.
- Isso pode introduzir diferenças entre browsers, cache, proxies e dispositivos.
- A jornada inicial correta pode depender do momento em que a hidratação termina.

### 4. Publicação demasiado permissiva

- Mesmo com proteções já adicionadas, a publicação ainda depende de vários scripts independentes.
- Falhas parciais podem passar despercebidas se não houver validação central forte.

## Arquitetura alvo

### Princípio

Substituir o modelo de "muitos scripts independentes com regras duplicadas" por um motor central de sincronização com configuração por competição.

### Estrutura proposta

```text
competition_config.py / competitions.json
    -> define competição, fase, série, aliases, regras especiais

sync_competitions.py
    -> motor único de sincronização
    -> busca fixtureIds
    -> descarrega jornadas
    -> valida
    -> normaliza
    -> publica

fpf_client.py
    -> requests/retries/backoff/bloqueios/caching

validators.py
    -> integridade estrutural e semântica

publish_state/
    -> snapshots válidos anteriores
    -> relatórios de execução
```

## Modelo de dados recomendado

Cada competição deve passar a ter três estados lógicos:

### 1. `raw`

Resposta original da origem para auditoria/debug.

- página principal da competição;
- fragmentos por `fixtureId`;
- metadados de fetch (`status`, `timestamp`, `source`, `attempts`).

### 2. `normalized`

Dados convertidos para o formato da app:

- `rounds[]`
- `matches[]`
- `classification[]`
- `defaultRoundIndex`
- `lastUpdatedAt`
- `sourceHealth`

### 3. `published`

Última versão validada e segura para servir ao frontend.

Regra importante:

- só publicar se a nova versão passar as validações;
- caso contrário, manter a última versão boa.

## Configuração por competição

Em vez de codificar regras em cada script, cada competição deve ser descrita por configuração:

```python
{
    "key": "iniciados-a",
    "competitionId": 28476,
    "seasonId": 105,
    "phase": "2ª FASE",
    "serie": "SÉRIE 1 - APURAMENTO CAMPEAO",
    "uiTitle": "Iniciados A - Sub15",
    "uiSubtitle": "Liga 2 Algarve Futebol (Fase de Campeão)",
    "highlightTeam": "CF Os Armacenenses - A",
    "teamAliases": {
        "CF Os Armacenenses - A": "CF Os Armacenenses"
    },
    "classificationMode": "remote"
}
```

Campos adicionais possíveis:

- `classificationMode = remote | derived_from_results`
- `ignoredTeams`
- `crestAliases`
- `displayNameOverrides`
- `roundSelectionMode`

## Motor central de sincronização

### Responsabilidades

- carregar configuração de todas as competições;
- obter página principal da FPF;
- localizar a fase/série correta;
- extrair `fixtureIds`;
- descarregar cada jornada com retries;
- reaproveitar jornadas válidas existentes quando uma falhar;
- recalcular classificação quando necessário;
- validar o payload final;
- escrever JSON final;
- gerar relatório global da execução.

### Comportamento mínimo obrigatório

Para cada jornada:

- se o fetch for bem-sucedido e válido, substituir a jornada;
- se o fetch falhar, reutilizar a jornada anterior pelo mesmo `fixtureId`;
- se o HTML vier vazio ou bloqueado, não apagar dados válidos;
- se surgirem novas jornadas, adicioná-las;
- se desaparecerem jornadas antigas sem justificação, bloquear publicação.

## Cliente HTTP mais robusto

O cliente de acesso à FPF deve concentrar:

- headers e impersonation;
- retries com backoff progressivo;
- deteção de `403`, `429` e páginas de challenge;
- limite por competição e por jornada;
- cache local para desenvolvimento;
- métricas de sucesso/falha.

Melhorias desejáveis:

- jitter no backoff;
- cooldown global quando a origem começa a bloquear;
- fallback de proxies apenas como último recurso;
- timeout curto por tentativa e timeout global por competição.

## Validações antes de publicar

### Estruturais

- JSON válido;
- `rounds` é array;
- todos os `fixtureId` existem;
- campos esperados existem em `matches` e `classification`.

### Semânticas

- o número total de jornadas não diminui sem motivo;
- uma jornada já conhecida não pode perder todos os jogos;
- classificações não podem ficar vazias em competições que normalmente as têm;
- a jornada mais recente não deve recuar no tempo;
- equipas já conhecidas não devem desaparecer da classificação sem explicação.

### Regras especiais

- nas competições sem classificação remota, recalcular a tabela a partir dos resultados;
- só usar jogos com resultado fechado;
- 3 pontos por vitória, 1 por empate, 0 por derrota.

## Jornada inicial no frontend

### Estado atual desejável

O frontend deve abrir sempre na jornada cuja data é imediatamente anterior à data atual.

### Evolução recomendada

Mesmo que o frontend mantenha uma salvaguarda, a jornada inicial ideal deve vir já resolvida do JSON publicado:

```json
{
  "defaultRoundIndex": 8,
  "lastUpdatedAt": "2026-05-04T19:30:00Z",
  "rounds": [...]
}
```

Isto traz vantagens:

- elimina diferenças entre desktop e mobile;
- reduz dependência de `hash` antigo;
- reduz dependência de parsing de datas no browser;
- evita comportamento diferente quando a hidratação remota termina mais tarde.

## Papel do frontend após a refatoração

O frontend deve tornar-se mais simples.

### Ideal

- carregar `data/<competition>.json`;
- abrir em `defaultRoundIndex`;
- renderizar imediatamente;
- opcionalmente mostrar `lastUpdatedAt`.

### Hidratação ao vivo

Deve passar a ser opcional e não estrutural.

Se continuar a existir:

- nunca deve alterar a navegação do utilizador;
- nunca deve substituir dados válidos por payload vazio;
- deve atualizar apenas o que estiver comprovadamente mais fresco.

## Automação

O workflow deve correr o motor central e produzir um relatório legível.

### O workflow deve:

- executar sincronização completa;
- guardar um resumo por competição;
- falhar explicitamente quando houver regressão estrutural;
- publicar apenas quando existirem outputs válidos;
- anexar relatório de execução ao resumo do GitHub Actions.

### O relatório deve incluir

- competições atualizadas;
- competições mantidas por fallback;
- competições falhadas;
- jornadas novas encontradas;
- jornadas reutilizadas;
- hora da última execução válida.

## Fases de implementação sugeridas

### Fase 1

- introduzir ficheiro central de configuração;
- criar motor único de sincronização;
- reaproveitar código existente de parsing;
- manter formato atual de JSON.

### Fase 2

- mover cálculo de `defaultRoundIndex` para o pipeline;
- publicar `lastUpdatedAt` e `sourceHealth`;
- reduzir dependência da hidratação remota no browser.

### Fase 3

- substituir progressivamente os `fetch_*.py` por wrappers mínimos ou removê-los;
- adicionar testes unitários aos parsers e validadores;
- criar snapshots de regressão.

### Fase 4

- adicionar alertas automáticos para falhas persistentes;
- opcionalmente expor uma API estática mais limpa para consumo futuro.

## Critérios de aceitação

Uma implementação futura deve ser considerada concluída quando:

- todas as competições usam o mesmo motor de sincronização;
- nenhuma competição perde dados válidos por causa de `403` ou falha parcial;
- a jornada inicial abre corretamente em desktop e mobile;
- a automação publica apenas snapshots validados;
- o relatório final permite perceber rapidamente o estado de cada competição.

## Recomendação prática

Se esta refatoração for executada, a prioridade correta é:

1. centralizar configuração;
2. centralizar sincronização e validação;
3. publicar `defaultRoundIndex` no JSON;
4. simplificar o frontend.

Essa ordem reduz risco e permite melhorias progressivas sem reescrever tudo de uma vez.
