# Microsite de Competições - CF Os Armacenenses

Microsite estático que agrega resultados, classificações e calendários das equipas do CF Os Armacenenses. O projeto oferece uma experiência leve que pode ser servida diretamente no GitHub Pages ou em qualquer alojamento estático.

## Funcionalidades

- Agregação de várias competições numa página principal com navegação dedicada por equipa.
- Visualização por jornada e tabelas de classificação com destaque automático para o CF Os Armacenenses.
- Dados publicados por competição (`data/*.json`) como fonte principal para todos os dispositivos.
- Agenda e resultados globais suportados por `data/calendar.json`.
- Estado global das competições suportado por `data/status.json`.
- Interface responsiva (CSS Grid) com suporte para títulos/subtítulos dinâmicos, alternância de tema claro/escuro e preferência persistida em `localStorage`.
- Atualização periódica de dados através de scrapers Python que consomem o site oficial da FPF.
- `localStorage` usado apenas como fallback quando o fetch do JSON publicado falha.
- Manifesto de emblemas para carregamento imediato dos logótipos de cada clube.

## Estrutura do projeto

- `index.html` e `*.html`: páginas estáticas para o hub principal e para cada competição.
- `main.js`: lógica de UI das páginas de competição, carregamento de dados publicados, gestão de tema e renderização dos componentes dinâmicos.
- `agenda.js`: lógica dedicada da Agenda/Resultados globais.
- `css/`: estilos principais (`css/style.css`) e ativos suplementares.
- `data/`: ficheiros JSON gerados pelos scrapers (`{competicao}.json`, `calendar.json`, `status.json`, `crests.json`) consumidos pelo frontend.
- `img/`: logótipos do clube, emblemas (`img/crests/`) e ícones utilizados nas páginas.
- `fetch_*.py`: wrappers específicos por competição, usados pelo workflow e por execuções manuais, que delegam no motor comum de sincronização.
- `competition_configs.py`: configuração central das competições, equipas do clube e metadados usados por fetch, agenda e planeamento.
- `competition_sync.py`: motor comum de sincronização que lê a FPF, normaliza jornadas/classificações e grava os JSON.
- `run_fetchers.py`: runner com validação, retries e relatório de execução.
- `plan_fetchers.py`: planeador adaptativo que decide que competições devem ser atualizadas em cada run.
- `build_calendar.py`: gera `data/calendar.json` para a Agenda/Resultados globais.
- `build_status.py`: gera `data/status.json` com o estado agregado das competições.
- `generate_crest_manifest.py`: gera automaticamente o mapa normalizado de emblemas em `data/crests.json`.
- `tools/`: utilitários de apoio (ex.: `tools/probe_fixture.py` para inspecionar fixtures da FPF).
- `.github/workflows/deploy-app.yml`: publica o site no GitHub Pages quando mudam frontend e/ou `data/`.
- `.github/workflows/update-data.yml`: workflow principal de sincronização de dados.
- `.github/workflows/retry-pending-results.yml`: follow-up de retries orientado pelo planner temporal.

## Pré-requisitos

- Python 3.9 ou superior com acesso à internet durante a execução dos scrapers.
- Permissões de escrita no diretório `data/` para armazenar os ficheiros gerados.

## Atualizar dados manualmente

1. Para atualizar uma competição isolada, execute o wrapper respetivo (ex.: `python fetch_juniores.py`).
2. Para atualizar várias competições com a mesma lógica do workflow, execute `python run_fetchers.py`.
3. Para regenerar a Agenda global depois de atualizar dados, execute `python build_calendar.py`.
4. Para regenerar o estado global das competições, execute `python build_status.py`.
5. Confirme os JSON atualizados em `data/` e valide se os valores foram normalizados corretamente (ex.: `python3 -m json.tool data/seniores.json`).
6. (Opcional) Se novos emblemas forem adicionados a `img/crests/`, execute `python generate_crest_manifest.py` para atualizar `data/crests.json`.
7. Caso ocorram conflitos de merge nos JSON, remova os marcadores (`<<<<<<<`, `=======`, `>>>>>>>`) e volte a executar o `fetch_*.py` respetivo para gerar um ficheiro limpo antes de o commitar.

## Visualizar localmente

- Abra qualquer `*.html` diretamente no navegador para verificações rápidas (pode ocorrer bloqueio CORS ao ler JSON).
- Para evitar CORS, sirva a pasta via HTTP simples: `python -m http.server` e aceda a `http://localhost:8000`.

## Automação com GitHub Actions

### `Deploy site`

- Publica o conteúdo estático no GitHub Pages.
- Dispara em alterações de frontend e em alterações publicadas em `data/**`.
- Garante que um commit manual em `data/*.json` chega efetivamente ao site.

### `Sync data`

- Pode ser acionado manualmente, em `push` relevante de código de sync, ou por `schedule`.
- Usa `plan_fetchers.py` para decidir que competições precisam mesmo de ser atualizadas.
- Executa uma vaga inicial leve através de `run_fetchers.py`, com foco em publicar cedo o que já estiver válido.
- Regera `data/calendar.json`, `data/status.json` e o manifesto de emblemas quando necessário.
- Realiza commit automático dos ficheiros alterados e publica o site.

### `Retry pending results and deploy`

- Arranca depois do `Sync data` quando o follow-up faz sentido.
- Reavalia o plano e só corre fetchers que continuem pendentes.
- Respeita `nextRecommendedFetchAt` calculado pelo planner adaptativo.
- Faz retries mais tarde sem bloquear a vaga inicial.

## Scripts auxiliares

- `fetch_fpf.py`: wrapper da competição `seniores`.
- `generate_crest_manifest.py`: cria o mapa normalizado entre nomes de clubes e emblemas.
- `competition_sync.py`: contém o parser partilhado e a lógica comum de sincronização das competições.
- `tools/probe_fixture.py`: descarrega o HTML bruto de um fixture da FPF para análise e guarda em `cache/`.

## Contribuir

1. Crie uma branch dedicada e assegure que os scrapers geram dados consistentes antes de submeter alterações.
2. Prefira assets otimizados (PNG ≤ 512px) ao adicionar emblemas.
3. Atualize a documentação (`README.md`, `ARQUITETURA.md`, `ROADMAP.md`) sempre que modificar fluxos ou dependências relevantes.
