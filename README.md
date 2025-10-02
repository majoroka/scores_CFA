# Microsite de Competições - CF Os Armacenenses

Este é um microsite estático para exibir os resultados e classificações das competições do clube.

## Como Atualizar os Dados

Os dados são obtidos a partir do site da FPF através de um script Python.

### Pré-requisitos

- Python 3.x instalado.

### Passos para Atualização

1.  **Configurar o Scraper**:
    - Abra o arquivo `fetch_fpf.py` (na raiz do projeto).
    - A `COMPETITION_URL` já está configurada. Se precisar de outra competição, altere esta linha.
2.  **Executar o Scraper**:
    - Navegue até a pasta raiz do projeto no seu terminal.
    - Execute o comando: `python fetch_fpf.py`
    - Isso irá buscar os dados, criar uma pasta `cache` com os arquivos HTML baixados e gerar o arquivo `data/seniores.json` atualizado.

3.  **Gerar Manifesto de Emblemas (Opcional)**:
    - Se você adicionou novos emblemas de clubes em `img/crests/`, execute `python generate_crest_manifest.py` para atualizar o `data/crests.json`.

## Como Visualizar Localmente

Como este é um site estático sem dependências de build, você pode visualizá-lo de duas formas:

1.  **Abrindo o `index.html` diretamente no navegador.** (Pode causar erros de CORS ao buscar os arquivos JSON).
2.  **Usando um servidor local simples (Recomendado)**:
    - No terminal, na pasta raiz do projeto, execute: `python -m http.server`
    - Abra o seu navegador e acesse `http://localhost:8000`.

## Automação (Para um Site Online)

Para manter os dados atualizados automaticamente num site publicado, a abordagem recomendada é usar um serviço de CI/CD como o **GitHub Actions**.

Um ficheiro de workflow (`.github/workflows/update-data.yml`) está incluído no projeto. Se o projeto for alojado no GitHub, este "robô" pode ser configurado para executar o script `fetch_fpf.py` em intervalos regulares (ex: a cada 4 horas), fazer commit do novo ficheiro `data/seniores.json` e publicar o site, garantindo que os dados estão sempre frescos sem qualquer intervenção manual.
