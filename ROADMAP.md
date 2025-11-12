# Roadmap

## Objetivos imediatos (0-1 mês)

- ✅ Corrigir o parser de classificação dos scrapers para garantir que todas as equipas aparecem nos JSON locais (resolvido em nov/2023).
- Consolidar um comando único (ex.: `python tools/run_fetchers.py`) que execute todos os `fetch_*.py` e produza um relatório de sucesso/falha por competição.
- Formalizar um ficheiro de configuração partilhado para IDs de competição/época, evitando duplicação de constantes em cada scraper.
- Adicionar validações automáticas aos JSON gerados (estrutura `rounds`, campos obrigatórios, tipos), falhando o workflow caso haja dados incompletos.
- Rever o manifesto de emblemas, garantindo que todos os clubes presentes nos JSON têm correspondência em `data/crests.json`.

## Próximos passos (1-3 meses)

- Introduzir testes unitários simples para as funções de parsing dos scrapers, facilitando a deteção de mudanças no HTML da FPF.
- Criar uma camada de serviço em `main.js` que armazene em `localStorage` a última versão dos dados carregados, permitindo fallback em modo offline.
- Melhorar a acessibilidade: acrescentar textos alternativos descritivos, focos visuais para navegação por teclado e labels claras nas tabs.
- Disponibilizar indicadores visuais na UI quando os dados forem atualizados por hidratação em tempo real (badge “Última atualização” por jornada).

## Visão futura (3+ meses)

- Internacionalização dos textos da interface e possibilidade de alternar entre português e inglês sem duplicar páginas.
- Permitir seleção de equipa favorita com vista filtrada (apenas jogos dessa equipa em todas as competições).
- Expor os dados num formato API (JSON estático ou endpoints serverless) para integração com outras plataformas do clube.
- Automatizar notificações (e-mail ou webhook) sempre que o workflow falhar ao atualizar dados, reduzindo tempo de reação da equipa.
