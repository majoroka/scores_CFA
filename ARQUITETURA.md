# Arquitetura do Projeto

## Visão Geral

O microsite é constituído por páginas estáticas HTML, uma folha de estilos comum e um único bundle JavaScript (`main.js`). As páginas consomem ficheiros JSON gerados previamente por scrapers Python que extraem informação do portal de resultados da Federação Portuguesa de Futebol (FPF). O resultado é um site sem dependências de build, facilmente servível por qualquer CDN ou pelo GitHub Pages.

## Frontend

- Cada página de competição (`seniores.html`, `juniores.html`, etc.) declara em `data-competition` a chave que identifica o ficheiro JSON correspondente (`data/{chave}.json`).
- `main.js` é carregado em todas as páginas e divide-se em dois blocos: `ThemeManager`, responsável por sincronizar o tema claro/escuro com `localStorage` e com a preferência do sistema operativo, e o motor da competição, que lê os dados, gere o estado da jornada ativa e renderiza resultados e classificação.
- Durante o carregamento (`DOMContentLoaded`), o script obtém `data/{competition}.json` e `data/crests.json`, inicializa o estado com a jornada mais relevante (com base nas datas) e ativa a navegação por hash (`#resultados-jX`, `#classificacao-jX`).
- As jornadas incluem identificadores `fixtureId` que permitem ao frontend tentar hidratar os dados com chamadas diretas ao endpoint `Competition/GetClassificationAndMatchesByFixture` da FPF. Existem três URLs de fallback (domínio direto e dois proxies) para contornar CORS. As respostas são parseadas no browser para atualizar resultados e classificação sem necessidade de recompilar o JSON local.
- A renderização é responsiva: o layout alterna automaticamente entre versões mobile e desktop, aplicando destaque visual à equipa CF Os Armacenenses e recuperando os emblemas a partir de `crests.json`.

## Dados e Armazenamento

- `data/{competicao}.json` contém um array `rounds` com a estrutura `{ index, fixtureId, matches[], classification[] }`. Cada jogo guarda equipas, data, hora, estádio e resultado; a classificação inclui métricas agregadas (jogos, vitórias, golos, pontos).
- `data/crests.json` é um mapa de nomes normalizados de clubes para caminhos relativos de imagem (`img/crests/*.png`). O frontend normaliza os nomes (remoção de acentos, pontuação e duplicação de espaços) antes de procurar neste mapa.
- A pasta `cache/` guarda HTML bruto das jornadas descarregado pelos scrapers Python. Pode ser reutilizado em execuções futuras ativando a flag `USE_CACHE` para reduzir chamadas à FPF durante o desenvolvimento.
- Os assets visuais vivem em `img/` (logótipo principal) e `img/crests/` (emblemas). A folha de estilos comum (`css/style.css`) aplica identidade consistente a todas as páginas.

## Scrapers e Geração de Conteúdo

- Cada ficheiro `fetch_<competicao>.py` herda o padrão de `fetch_fpf.py`: descarrega a página da competição na FPF, encontra todos os `fixtureId`, obtém o HTML de cada jornada e extrai resultados e classificação para JSON. Os IDs de competição/época e o ficheiro de saída são configuráveis no topo de cada script.
- Os scrapers tratam das normalizações básicas (remoção de `<br>`, trimming, parsing de pontuações). Variações no HTML da FPF podem exigir ajustes nas regex; por isso, cada script isola a lógica de parsing para facilitar manutenção.
- `generate_crest_manifest.py` percorre `img/crests/`, normaliza os nomes de ficheiros (retirando acentos e símbolos) e cria o manifesto `data/crests.json`, adicionando aliases para variações comuns dos nomes.
- `tools/probe_fixture.py` é um utilitário rápido para descarregar o HTML de um `fixtureId` específico, gravando a resposta em `cache/fixture_<id>.html` para apoiar a criação ou debugging dos scrapers.

## Automação e Deploy

- O workflow `.github/workflows/update-data.yml` é o coração da automação: corre manualmente ou a cada 4 horas, executa todos os `fetch_*.py` com timeout controlado, regenera o manifesto de emblemas e faz commit automático das alterações em `data/`.
- Após os dados serem atualizados, o workflow publica a versão estática do site usando GitHub Pages (`actions/deploy-pages`). Como não existem etapas de build, o artefacto enviado corresponde à árvore de ficheiros do repositório.

## Fluxo de Desenvolvimento

- Para adicionar uma nova competição, crie a respetiva página HTML (copiando um template existente), defina a chave `data-competition`, implemente um novo `fetch_<competicao>.py` ou ajuste um existente com os IDs corretos e execute-o para gerar `data/<competicao>.json`.
- Ao introduzir novos emblemas, coloque o ficheiro PNG em `img/crests/` seguindo a nomenclatura "Equipa.png", depois execute `python generate_crest_manifest.py` para atualizar o manifesto.
- Qualquer alteração estruturante no JSON ou na renderização deve ser refletida em testes manuais (carregando a página localmente) e, quando aplicável, documentada no `README.md` e no `ROADMAP.md`.
