# Microsite de Competições - CF Os Armacenenses

Microsite estático que agrega resultados, classificações e calendários das equipas do CF Os Armacenenses. O projeto oferece uma experiência leve que pode ser servida diretamente no GitHub Pages ou em qualquer alojamento estático.

## Funcionalidades

- Agregação de várias competições numa página principal com navegação dedicada por equipa.
- Visualização por jornada e tabelas de classificação com destaque automático para o CF Os Armacenenses.
- Dados publicados por competição (`data/*.json`) como fonte principal para todos os dispositivos.
- Agenda e resultados globais suportados por `data/calendar.json`.
- Estado global das competições suportado por `data/status.json`.
- Interface responsiva (CSS Grid) com suporte para títulos/subtítulos dinâmicos, alternância de tema claro/escuro e preferência persistida em `localStorage`.
- Atualização manual de dados através de scrapers Python executados localmente contra o site oficial da FPF.
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

## Pré-requisitos

- Python 3.9 ou superior com acesso à internet durante a execução dos scrapers.
- Permissões de escrita no diretório `data/` para armazenar os ficheiros gerados.

## Atualizar dados manualmente

1. Atualize uma competição isolada com o wrapper respetivo (ex.: `python3 fetch_juniores.py`).
2. Depois de qualquer `fetch_*.py`, execute sempre:
   - `python3 build_calendar.py`
   - `python3 build_status.py`
3. Faça `git add`, `git commit` e `git push` dos ficheiros alterados em `data/`.
4. Confirme os JSON atualizados em `data/` e valide se os valores foram normalizados corretamente (ex.: `python3 -m json.tool data/seniores.json`).
5. (Opcional) Se novos emblemas forem adicionados a `img/crests/`, execute `python generate_crest_manifest.py` para atualizar `data/crests.json`.
6. Caso ocorram conflitos de merge nos JSON, remova os marcadores (`<<<<<<<`, `=======`, `>>>>>>>`) e volte a executar o `fetch_*.py` respetivo para gerar um ficheiro limpo antes de o commitar.
7. Para comandos prontos por competição, use [MANUAL_FETCH_COMMANDS.txt](/Users/mariocabano/Documents/GitHub/scores_CFA/MANUAL_FETCH_COMMANDS.txt).

## Visualizar localmente

- Abra qualquer `*.html` diretamente no navegador para verificações rápidas (pode ocorrer bloqueio CORS ao ler JSON).
- Para evitar CORS, sirva a pasta via HTTP simples: `python -m http.server` e aceda a `http://localhost:8000`.

## GitHub Actions

### `Deploy site`

- Publica o conteúdo estático no GitHub Pages.
- Dispara em alterações de frontend e em alterações publicadas em `data/**`.
- Garante que um commit manual em `data/*.json` chega efetivamente ao site.

Neste momento, os workflows automáticos de scraping foram removidos/desligados. O scraping é efetuado manualmente no computador do utilizador e o GitHub fica responsável apenas por publicar o site após `push`.

## Scripts auxiliares

- `fetch_seniores.py`: wrapper da competição `seniores`.
- `generate_crest_manifest.py`: cria o mapa normalizado entre nomes de clubes e emblemas.
- `competition_sync.py`: contém o parser partilhado e a lógica comum de sincronização das competições.
- `tools/probe_fixture.py`: descarrega o HTML bruto de um fixture da FPF para análise e guarda em `cache/`.

## Contribuir

1. Crie uma branch dedicada e assegure que os scrapers geram dados consistentes antes de submeter alterações.
2. Prefira assets otimizados (PNG ≤ 512px) ao adicionar emblemas.
3. Atualize a documentação (`README.md`, `ARQUITETURA.md`, `ROADMAP.md`) sempre que modificar fluxos ou dependências relevantes.

## Documentos de referência

- [ARQUITETURA.md](/Users/mariocabano/Documents/GitHub/scores_CFA/ARQUITETURA.md): visão geral da arquitetura atual.
- [FEATURE_AGENDA_RESULTADOS.md](/Users/mariocabano/Documents/GitHub/scores_CFA/FEATURE_AGENDA_RESULTADOS.md): comportamento atual da Agenda/Resultados globais.
- [ROADMAP.md](/Users/mariocabano/Documents/GitHub/scores_CFA/ROADMAP.md): prioridades atuais após a transição para scraping manual local.
- [MANUAL_FETCH_COMMANDS.txt](/Users/mariocabano/Documents/GitHub/scores_CFA/MANUAL_FETCH_COMMANDS.txt): comandos manuais por competição e builds agregados.
