# Scores CFA

Microsite estático do CF Os Armacenenses para consultar jogos, resultados e classificações. A aplicação não executa scraping nem transforma dados no servidor: lê diretamente ficheiros JSON preparados externamente e publicados com o site.

## Funcionalidades

- lista de competições gerada a partir de um catálogo único;
- página genérica de competição com jornadas, jogos e classificação;
- Agenda global, com intervalo de datas e filtro por competição;
- destaque automático das equipas do CF Os Armacenenses;
- diagnóstico da integridade dos ficheiros em `admin.html`;
- temas claro e escuro e apresentação responsiva;
- publicação automática no GitHub Pages após `push`.

## Dados

O catálogo ativo está em:

```text
data/competitions/index.json
```

Os ficheiros da época 2026-2027 estão em:

```text
data/competitions/2026-2027/
```

Regras:

- nomes de ficheiro em minúsculas, ASCII e separados por hífen;
- um ficheiro por competição/série;
- a época fica no diretório e não precisa de ser repetida no nome;
- apenas competições com `enabled: true` no catálogo aparecem na app;
- `teamNames` identifica exatamente a equipa do clube nessa competição;
- `accent` define a cor usada no cartão e no badge da competição.

O formato esperado é `fpf-browser-single-series-v2`, com pelo menos:

```text
captured_at
source
validation.complete
teams
rounds[].round
rounds[].fixtureId
rounds[].games[]
rounds[].classification[]
```

## Adicionar Ou Atualizar Uma Competição

1. Colocar ou substituir o JSON em `data/competitions/<epoca>/`.
2. Criar ou atualizar a entrada correspondente em `data/competitions/index.json`.
3. Validar o JSON com `jq empty <ficheiro>`.
4. Servir a app localmente e confirmar página, Agenda e diagnóstico.
5. Fazer commit e `git push origin main`.

Não é necessário gerar `calendar.json`, `status.json` ou uma página HTML por competição. A Agenda e o diagnóstico são calculados no browser a partir do catálogo.

## Desenvolvimento Local

Como o browser carrega JSON por `fetch`, a app deve ser servida por HTTP:

```bash
cd /Users/mariocabano/Documents/GitHub/scores_CFA
python3 -m http.server 8000
```

Abrir `http://localhost:8000`.

## Estrutura

- `index.html`: lista dinâmica de competições.
- `competition.html`: página genérica de qualquer competição.
- `agenda.html`: Agenda e Resultados globais.
- `admin.html`: diagnóstico dos ficheiros ativos.
- `data-service.js`: validação, normalização e agregação dos JSON.
- `main.js`: tema, página inicial e detalhe da competição.
- `agenda.js`: filtros e renderização da Agenda.
- `admin.js`: diagnóstico calculado a partir dos JSON.
- `data/competitions/`: catálogo e ficheiros por época.
- `data/crests.json`: mapa de nomes normalizados para emblemas.
- `generate_crest_manifest.py`: utilitário opcional para regenerar o manifesto de emblemas.
- `.github/workflows/deploy-app.yml`: único workflow, dedicado ao GitHub Pages.

## Documentação

- [ARQUITETURA.md](ARQUITETURA.md)
- [FEATURE_AGENDA_RESULTADOS.md](FEATURE_AGENDA_RESULTADOS.md)
- [ROADMAP.md](ROADMAP.md)
