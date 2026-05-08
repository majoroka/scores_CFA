from dataclasses import dataclass, field
from typing import FrozenSet


@dataclass(frozen=True)
class CompetitionConfig:
    competition_url: str
    output_file: str
    main_cache_key: str
    fixture_cache_prefix: str
    target_serie_name: str = ''
    target_phase_name: str = ''
    target_serie_id: str = ''
    allow_first_block_fallback: bool = False
    derive_classification: bool = False
    ignored_team_names: FrozenSet[str] = field(default_factory=frozenset)
    strip_score_from_date: bool = False
    club_team_names: FrozenSet[str] = field(default_factory=frozenset)
    key: str = ''
    title: str = ''
    subtitle: str = ''
    page_path: str = ''


BENJAMINS_A1 = CompetitionConfig(
    key='benjamins-a1',
    title='Benjamins A1 – Sub11',
    subtitle='Liga Algarve Futebol 7 (2ª Fase - Série 3)',
    page_path='benjamins-a1.html',
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28744&seasonId=105',
    output_file='data/benjamins-a1.json',
    main_cache_key='benjamins_a1_competition_main',
    fixture_cache_prefix='benjamins_a1_fixture',
    target_phase_name='2ª FASE',
    target_serie_name='SÉRIE 3',
    derive_classification=True,
    ignored_team_names=frozenset({'a indicar'}),
    strip_score_from_date=True,
    club_team_names=frozenset({'Cf Os Armacenenses'}),
)

BENJAMINS_A2 = CompetitionConfig(
    key='benjamins-a2',
    title='Benjamins A2 – Sub11',
    subtitle='Liga Algarve Futebol 7 (2ª Fase - Série 10)',
    page_path='benjamins-a2.html',
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28744&seasonId=105',
    output_file='data/benjamins-a2.json',
    main_cache_key='benjamins_a2_competition_main',
    fixture_cache_prefix='benjamins_a2_fixture',
    target_phase_name='2ª FASE',
    target_serie_name='SÉRIE 10',
    derive_classification=True,
    ignored_team_names=frozenset({'a indicar'}),
    strip_score_from_date=True,
    club_team_names=frozenset({'Cf Os Armacenenses'}),
)

BENJAMINS_B = CompetitionConfig(
    key='benjamins-b',
    title='Benjamins B – Sub10',
    subtitle='Liga Algarve Futebol 7 (2ª Fase – Série 2)',
    page_path='benjamins-b.html',
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28750&seasonId=105',
    output_file='data/benjamins-b.json',
    main_cache_key='benjamins_b_competition_main',
    fixture_cache_prefix='benjamins_b_fixture',
    target_serie_name='SÉRIE 2',
    derive_classification=True,
    ignored_team_names=frozenset({'a indicar'}),
    strip_score_from_date=True,
    club_team_names=frozenset({'Cf Os Armacenenses'}),
)

BENJAMINS_BB = CompetitionConfig(
    key='benjamins-bb',
    title='Benjamins BB – Sub10',
    subtitle='Liga Algarve Futebol 7 (2ª Fase – Série 6)',
    page_path='benjamins-bb.html',
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28750&seasonId=105',
    output_file='data/benjamins-bb.json',
    main_cache_key='benjamins_bb_competition_main',
    fixture_cache_prefix='benjamins_bb_fixture',
    target_serie_name='SÉRIE 6',
    derive_classification=True,
    ignored_team_names=frozenset({'a indicar'}),
    strip_score_from_date=True,
    club_team_names=frozenset({'Cf Os Armacenenses'}),
)

FEMININO_SUB15 = CompetitionConfig(
    key='feminino-sub15',
    title='Feminino – Sub15',
    subtitle='Liga Algarve Futebol 9 (2ª Fase – Série 4)',
    page_path='feminino-sub15.html',
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28562&seasonId=105',
    output_file='data/feminino-sub15.json',
    main_cache_key='feminino_sub15_competition_main',
    fixture_cache_prefix='feminino_sub15_fixture',
    target_serie_name='SÉRIE 4',
    allow_first_block_fallback=True,
    club_team_names=frozenset({'Cf Os Armacenenses'}),
)

FEMININO_SUB17 = CompetitionConfig(
    key='feminino-sub17',
    title='Feminino – Sub17',
    subtitle='Liga 2 Algarve Futebol (2ª Fase - Série 7)',
    page_path='feminino-sub17.html',
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28476&seasonId=105',
    output_file='data/feminino-sub17.json',
    main_cache_key='feminino_sub17_competition_main',
    fixture_cache_prefix='feminino_sub17_fixture',
    target_phase_name='2ª FASE',
    target_serie_name='SÉRIE 7',
    club_team_names=frozenset({'Cf Os Armacenenses - A', 'Cf Os Armacenenses - B'}),
)

FEMININO_SUB19 = CompetitionConfig(
    key='feminino-sub19',
    title='Feminino - Sub19',
    subtitle='Taça Nacional (1ª Fase – Série H)',
    page_path='feminino-sub19.html',
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=24932&seasonId=105',
    output_file='data/feminino-sub19.json',
    main_cache_key='feminino_sub19_competition_main_105',
    fixture_cache_prefix='feminino_sub19_fixture',
    target_serie_name='1ª FASE-SÉRIE H',
    club_team_names=frozenset({'Cf Os Armacenenses'}),
)

SENIORES = CompetitionConfig(
    key='seniores',
    title='Seniores',
    subtitle='Liga 1 Algarve Futebol (2ª Fase - Manutenção/Descida)',
    page_path='seniores.html',
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28206&seasonId=105',
    output_file='data/seniores.json',
    main_cache_key='seniores_competition_main',
    fixture_cache_prefix='seniores_fixture',
    target_serie_name='MANUTENÇÃO/DESCIDA',
    club_team_names=frozenset({'Cf Os Armacenenses'}),
)

INFANTIS_A = CompetitionConfig(
    key='infantis-a',
    title='Infantis A – Sub13',
    subtitle='Liga 2 Algarve Futebol (2ª Fase - Série 2)',
    page_path='infantis-a.html',
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28562&seasonId=105',
    output_file='data/infantis-a.json',
    main_cache_key='infantis_a_competition_main',
    fixture_cache_prefix='infantis_a_fixture',
    target_serie_name='SÉRIE 2',
    club_team_names=frozenset({'Cf Os Armacenenses'}),
)

INFANTIS_B = CompetitionConfig(
    key='infantis-b',
    title='Infantis B – Sub12',
    subtitle='Liga 2 Algarve Futebol (2ª Fase – Série 2)',
    page_path='infantis-b.html',
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28563&seasonId=105',
    output_file='data/infantis-b.json',
    main_cache_key='infantis_b_competition_main',
    fixture_cache_prefix='infantis_b_fixture',
    target_serie_name='SÉRIE 2',
    club_team_names=frozenset({'Cf Os Armacenenses'}),
)

INFANTIS_C = CompetitionConfig(
    key='infantis-c',
    title='Infantis C – Sub12',
    subtitle='Liga Algarve Futebol 7 (Fase de Campeão)',
    page_path='infantis-c.html',
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28724&seasonId=105',
    output_file='data/infantis-c.json',
    main_cache_key='infantis_c_competition_main',
    fixture_cache_prefix='infantis_c_fixture',
    target_serie_name='APURAMENTO CAMPEÃO',
    club_team_names=frozenset({'Cf Os Armacenenses'}),
)

INICIADOS_A = CompetitionConfig(
    key='iniciados-a',
    title='Iniciados A – Sub15',
    subtitle='Liga 2 Algarve Futebol (Fase de Campeão)',
    page_path='iniciados-a.html',
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28476&seasonId=105',
    output_file='data/iniciados-a.json',
    main_cache_key='iniciados_a_competition_main',
    fixture_cache_prefix='iniciados_a_fixture',
    target_phase_name='2ª FASE',
    target_serie_name='SÉRIE 1 - APURAMENTO CAMPEAO',
    club_team_names=frozenset({'Cf Os Armacenenses'}),
)

INICIADOS_B = CompetitionConfig(
    key='iniciados-b',
    title='Iniciados B – Sub15',
    subtitle='Liga 2 Algarve Futebol (2ª Fase - Série 7)',
    page_path='iniciados-b.html',
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28476&seasonId=105',
    output_file='data/iniciados-b.json',
    main_cache_key='iniciados_b_competition_main',
    fixture_cache_prefix='iniciados_b_fixture',
    target_phase_name='2ª FASE',
    target_serie_name='SÉRIE 7',
    club_team_names=frozenset({'Cf Os Armacenenses - A'}),
)

JUNIORES = CompetitionConfig(
    key='juniores',
    title='Juniores - Sub19',
    subtitle='Liga Algarve Futebol (Fase de Campeão)',
    page_path='juniores.html',
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28263&seasonId=105',
    output_file='data/juniores.json',
    main_cache_key='juniores_competition_main',
    fixture_cache_prefix='juniores_fixture',
    target_serie_name='APURAMENTO CAMPEÃO',
    club_team_names=frozenset({'Cf Os Armacenenses'}),
)

JUVENIS = CompetitionConfig(
    key='juvenis',
    title='Juvenis - Sub17',
    subtitle='Liga 2 Algarve Futebol (2ª Fase - Série 3)',
    page_path='juvenis.html',
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28459&seasonId=105',
    output_file='data/juvenis.json',
    main_cache_key='juvenis_competition_main',
    fixture_cache_prefix='juvenis_fixture',
    target_serie_name='SÉRIE 3',
    club_team_names=frozenset({'Cf Os Armacenenses'}),
)


ALL_COMPETITIONS = (
    SENIORES,
    JUNIORES,
    JUVENIS,
    INICIADOS_A,
    INICIADOS_B,
    INFANTIS_A,
    INFANTIS_B,
    INFANTIS_C,
    BENJAMINS_A1,
    BENJAMINS_A2,
    BENJAMINS_B,
    BENJAMINS_BB,
    FEMININO_SUB19,
    FEMININO_SUB17,
    FEMININO_SUB15,
)
