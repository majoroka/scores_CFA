# Roadmap

## Objetivos imediatos (0-1 mês)

- ✅ Corrigir o parser de classificação dos scrapers para garantir que todas as equipas aparecem nos JSON locais (resolvido em nov/2023).
- ✅ Refatorizar cabeçalho das páginas de detalhe (CSS Grid) para suportar subtítulos de fases extensos (resolvido em jan/2025).
- ✅ Atualizar scrapers para as novas fases das competições (Infantis, Femininos) (resolvido em jan/2025).
- ✅ Consolidar um motor único de sincronização e configuração central por competição (`competition_sync.py` + `competition_configs.py`).
- ✅ Adicionar validações automáticas, retries e relatório por fetcher através de `run_fetchers.py`.
- ✅ Publicar metadata de sincronização nos JSON (`defaultRoundIndex`, `defaultRoundNumber`, `lastUpdatedAt`, `sourceHealth`).
- ✅ Introduzir testes unitários e testes de regressão com snapshots reais da FPF.
- Monitorizar e adaptar scrapers para futuras fases e competições (ex: Taças Nacionais, Fases de Manutenção).
- Rever o manifesto de emblemas, garantindo que todos os clubes presentes nos JSON têm correspondência em `data/crests.json`.

## Próximos passos (1-3 meses)

- Mostrar `lastUpdatedAt` e `sourceHealth` na UI para dar visibilidade ao estado real dos dados.
- Definir uma política operacional para `DEGRADED` no workflow: apenas informar, falhar acima de limiar ou acionar alerta.
- Alargar a biblioteca de snapshots reais da FPF a mais famílias de competição e mais casos-limite.
- Criar uma camada de serviço em `main.js` que armazene em `localStorage` a última versão dos dados carregados, permitindo fallback em modo offline.
- Melhorar a acessibilidade: acrescentar textos alternativos descritivos, focos visuais para navegação por teclado e labels claras nas tabs.

## Visão futura (3+ meses)

- Internacionalização dos textos da interface e possibilidade de alternar entre português e inglês sem duplicar páginas.
- Permitir seleção de equipa favorita com vista filtrada (apenas jogos dessa equipa em todas as competições).
- Expor os dados num formato API (JSON estático ou endpoints serverless) para integração com outras plataformas do clube.
- Automatizar notificações (e-mail ou webhook) sempre que o workflow falhar ao atualizar dados, reduzindo tempo de reação da equipa.
