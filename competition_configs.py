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


BENJAMINS_A1 = CompetitionConfig(
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28744&seasonId=105',
    output_file='data/benjamins-a1.json',
    main_cache_key='benjamins_a1_competition_main',
    fixture_cache_prefix='benjamins_a1_fixture',
    target_phase_name='2ª FASE',
    target_serie_name='SÉRIE 3',
    derive_classification=True,
    ignored_team_names=frozenset({'a indicar'}),
    strip_score_from_date=True,
)

BENJAMINS_A2 = CompetitionConfig(
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28744&seasonId=105',
    output_file='data/benjamins-a2.json',
    main_cache_key='benjamins_a2_competition_main',
    fixture_cache_prefix='benjamins_a2_fixture',
    target_phase_name='2ª FASE',
    target_serie_name='SÉRIE 10',
    derive_classification=True,
    ignored_team_names=frozenset({'a indicar'}),
    strip_score_from_date=True,
)

BENJAMINS_B = CompetitionConfig(
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28750&seasonId=105',
    output_file='data/benjamins-b.json',
    main_cache_key='benjamins_b_competition_main',
    fixture_cache_prefix='benjamins_b_fixture',
    target_serie_name='SÉRIE 2',
    derive_classification=True,
    ignored_team_names=frozenset({'a indicar'}),
    strip_score_from_date=True,
)

BENJAMINS_BB = CompetitionConfig(
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28750&seasonId=105',
    output_file='data/benjamins-bb.json',
    main_cache_key='benjamins_bb_competition_main',
    fixture_cache_prefix='benjamins_bb_fixture',
    target_serie_name='SÉRIE 6',
    derive_classification=True,
    ignored_team_names=frozenset({'a indicar'}),
    strip_score_from_date=True,
)

FEMININO_SUB15 = CompetitionConfig(
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28562&seasonId=105',
    output_file='data/feminino-sub15.json',
    main_cache_key='feminino_sub15_competition_main',
    fixture_cache_prefix='feminino_sub15_fixture',
    target_serie_name='SÉRIE 4',
    allow_first_block_fallback=True,
)

FEMININO_SUB17 = CompetitionConfig(
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28476&seasonId=105',
    output_file='data/feminino-sub17.json',
    main_cache_key='feminino_sub17_competition_main',
    fixture_cache_prefix='feminino_sub17_fixture',
    target_phase_name='2ª FASE',
    target_serie_name='SÉRIE 7',
)

FEMININO_SUB19 = CompetitionConfig(
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=24932&seasonId=105',
    output_file='data/feminino-sub19.json',
    main_cache_key='feminino_sub19_competition_main_105',
    fixture_cache_prefix='feminino_sub19_fixture',
    target_serie_name='1ª FASE-SÉRIE H',
)

SENIORES = CompetitionConfig(
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28206&seasonId=105',
    output_file='data/seniores.json',
    main_cache_key='seniores_competition_main',
    fixture_cache_prefix='seniores_fixture',
    target_serie_name='MANUTENÇÃO/DESCIDA',
)

INFANTIS_A = CompetitionConfig(
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28562&seasonId=105',
    output_file='data/infantis-a.json',
    main_cache_key='infantis_a_competition_main',
    fixture_cache_prefix='infantis_a_fixture',
    target_serie_name='SÉRIE 2',
)

INFANTIS_B = CompetitionConfig(
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28563&seasonId=105',
    output_file='data/infantis-b.json',
    main_cache_key='infantis_b_competition_main',
    fixture_cache_prefix='infantis_b_fixture',
    target_serie_name='SÉRIE 2',
)

INFANTIS_C = CompetitionConfig(
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28724&seasonId=105',
    output_file='data/infantis-c.json',
    main_cache_key='infantis_c_competition_main',
    fixture_cache_prefix='infantis_c_fixture',
    target_serie_name='APURAMENTO CAMPEÃO',
)

INICIADOS_A = CompetitionConfig(
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28476&seasonId=105',
    output_file='data/iniciados-a.json',
    main_cache_key='iniciados_a_competition_main',
    fixture_cache_prefix='iniciados_a_fixture',
    target_phase_name='2ª FASE',
    target_serie_name='SÉRIE 1 - APURAMENTO CAMPEAO',
)

INICIADOS_B = CompetitionConfig(
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28476&seasonId=105',
    output_file='data/iniciados-b.json',
    main_cache_key='iniciados_b_competition_main',
    fixture_cache_prefix='iniciados_b_fixture',
    target_phase_name='2ª FASE',
    target_serie_name='SÉRIE 7',
)

JUNIORES = CompetitionConfig(
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28263&seasonId=105',
    output_file='data/juniores.json',
    main_cache_key='juniores_competition_main',
    fixture_cache_prefix='juniores_fixture',
    target_serie_name='APURAMENTO CAMPEÃO',
)

JUVENIS = CompetitionConfig(
    competition_url='https://resultados.fpf.pt/Competition/Details?competitionId=28459&seasonId=105',
    output_file='data/juvenis.json',
    main_cache_key='juvenis_competition_main',
    fixture_cache_prefix='juvenis_fixture',
    target_serie_name='SÉRIE 3',
)
