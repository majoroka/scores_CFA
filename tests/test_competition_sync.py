import unittest
from datetime import datetime
from pathlib import Path

from competition_configs import CompetitionConfig, FEMININO_SUB15, INICIADOS_A
from competition_sync import (
    build_payload,
    collect_quality_metrics,
    compute_default_round_index,
    extract_fixture_ids,
    fill_missing_scores_from_secondary_results,
    infer_payload_status,
    parse_classification,
    parse_match_date,
    parse_matches,
    parse_zerozero_round_results,
)


class CompetitionSyncTests(unittest.TestCase):
    fixtures_dir = Path(__file__).resolve().parent / 'fixtures' / 'fpf'

    @classmethod
    def read_fixture(cls, name):
        return (cls.fixtures_dir / name).read_text(encoding='utf-8')

    def test_extract_fixture_ids_with_phase_and_series(self):
        html = '''
        <div class="accordion-title">1ª FASE</div>
        <div class="game-results" id="htmlSerieId_111">
            <a href="/Competition/GetClassificationAndMatchesByFixture?fixtureId=1001">J1</a>
        </div>
        <div class="accordion-title">2ª FASE</div>
        <div class="game-results" id="htmlSerieId_222">
            <h3>SÉRIE 7</h3>
            <a href="/Competition/GetClassificationAndMatchesByFixture?fixtureId=2001">J1</a>
            <a href="/Competition/GetClassificationAndMatchesByFixture?fixtureId=2002">J2</a>
        </div>
        '''
        config = CompetitionConfig(
            competition_url='https://example.test',
            output_file='data/example.json',
            main_cache_key='example_main',
            fixture_cache_prefix='example_fixture',
            target_phase_name='2ª FASE',
            target_serie_name='SÉRIE 7',
        )
        self.assertEqual(extract_fixture_ids(html, config), ['2001', '2002'])

    def test_extract_fixture_ids_with_first_block_fallback(self):
        html = '''
        <div class="game-results" id="htmlSerieId_555">
            <a href="/Competition/GetClassificationAndMatchesByFixture?fixtureId=3001">J1</a>
            <a href="/Competition/GetClassificationAndMatchesByFixture?fixtureId=3002">J2</a>
        </div>
        '''
        config = CompetitionConfig(
            competition_url='https://example.test',
            output_file='data/example.json',
            main_cache_key='example_main',
            fixture_cache_prefix='example_fixture',
            target_serie_name='SÉRIE 4',
            allow_first_block_fallback=True,
        )
        self.assertEqual(extract_fixture_ids(html, config), ['3001', '3002'])

    def test_parse_matches_can_strip_score_from_date(self):
        fragment = '''
        <div class="game">
            <div class="home-team">Casa FC</div>
            <div class="text-center">2 - 1 3 mai 10:30</div>
            <div class="away-team">Fora FC</div>
        </div>
        <div class="game-list-stadium"><small>Campo A</small></div>
        '''
        matches = parse_matches(fragment, strip_score_from_date=True)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['home'], 'Casa FC')
        self.assertEqual(matches[0]['away'], 'Fora FC')
        self.assertEqual(matches[0]['homeScore'], 2)
        self.assertEqual(matches[0]['awayScore'], 1)
        self.assertEqual(matches[0]['date'], '3 mai')
        self.assertEqual(matches[0]['time'], '10:30')

    def test_parse_classification_reads_all_columns(self):
        fragment = '''
        <div id="classification">
            <div class="game classification row">
                <div class="col-md-1">1</div>
                <div class="col-md-4">Cf Os Armacenenses</div>
                <div class="col-md-1">10</div>
                <div class="col-md-1">8</div>
                <div class="col-md-1">1</div>
                <div class="col-md-1">1</div>
                <div class="col-md-1">25</div>
                <div class="col-md-1">9</div>
                <div class="col-md-1">25</div>
            </div>
        </div>
        <div id="matches"></div>
        '''
        classification = parse_classification(fragment)
        self.assertEqual(classification, [{
            'position': 1,
            'team': 'Cf Os Armacenenses',
            'played': 10,
            'wins': 8,
            'draws': 1,
            'losses': 1,
            'goalsFor': 25,
            'goalsAgainst': 9,
            'points': 25,
        }])

    def test_parse_match_date_ignores_embedded_score(self):
        parsed = parse_match_date('2 - 1 3 mai', today=datetime(2026, 5, 7, 12, 0, 0))
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.year, 2026)
        self.assertEqual(parsed.month, 5)
        self.assertEqual(parsed.day, 3)

    def test_compute_default_round_index_prefers_latest_past_round(self):
        rounds = [
            {'index': 1, 'matches': [{'date': '10 jan', 'homeScore': 1, 'awayScore': 0}]},
            {'index': 2, 'matches': [{'date': '2 mai', 'homeScore': 4, 'awayScore': 2}]},
            {'index': 3, 'matches': [{'date': '23 mai', 'homeScore': None, 'awayScore': None}]},
        ]
        result = compute_default_round_index(rounds, today=datetime(2026, 5, 7, 12, 0, 0))
        self.assertEqual(result, 1)

    def test_build_payload_includes_metadata(self):
        rounds = [
            {'index': 1, 'matches': [{'date': '10 jan', 'homeScore': 1, 'awayScore': 0}]},
            {'index': 2, 'matches': [{'date': '2 mai', 'homeScore': 4, 'awayScore': 2}]},
        ]
        payload = build_payload(
            rounds,
            fallback_reuse_count=2,
            last_updated_at='2026-05-07T15:00:00Z',
        )
        self.assertEqual(payload['defaultRoundIndex'], 1)
        self.assertEqual(payload['defaultRoundNumber'], 2)
        self.assertEqual(payload['lastUpdatedAt'], '2026-05-07T15:00:00Z')
        self.assertEqual(payload['sourceHealth']['status'], 'degraded')
        self.assertEqual(payload['sourceHealth']['fallbackReuseCount'], 2)
        self.assertIn('dataQuality', payload)
        self.assertEqual(payload['dataQuality']['completedMatchCount'], 2)
        self.assertEqual(payload['rounds'], rounds)

    def test_collect_quality_metrics_counts_past_matches_without_score(self):
        rounds = [
            {
                'index': 1,
                'matches': [
                    {'home': 'Casa', 'away': 'Fora', 'date': '2 mai', 'homeScore': 1, 'awayScore': 0},
                    {'home': 'Casa B', 'away': 'Fora B', 'date': '3 mai', 'homeScore': None, 'awayScore': None},
                ],
                'classification': [{'team': 'Casa'}],
            },
            {
                'index': 2,
                'matches': [
                    {'home': 'Casa C', 'away': 'Fora C', 'date': '23 mai', 'homeScore': None, 'awayScore': None},
                ],
                'classification': [],
            },
        ]
        metrics = collect_quality_metrics(rounds, today=datetime(2026, 5, 7, 12, 0, 0))
        self.assertEqual(metrics['roundCount'], 2)
        self.assertEqual(metrics['matchCount'], 3)
        self.assertEqual(metrics['completedMatchCount'], 1)
        self.assertEqual(metrics['matchesWithoutScore'], 2)
        self.assertEqual(metrics['pastMatchesWithoutScore'], 1)
        self.assertEqual(metrics['futureMatchCount'], 1)
        self.assertEqual(metrics['teamCount'], 6)

    def test_infer_payload_status_distinguishes_partial_from_degraded(self):
        self.assertEqual(
            infer_payload_status(1, {'pastMatchesWithoutScore': 0}),
            'degraded',
        )
        self.assertEqual(
            infer_payload_status(0, {'pastMatchesWithoutScore': 2}),
            'partial',
        )
        self.assertEqual(
            infer_payload_status(0, {'pastMatchesWithoutScore': 0}),
            'ok',
        )

    def test_real_main_page_extracts_iniciados_a_fixture_ids(self):
        html = self.read_fixture('competition_iniciados_a_main.html')
        fixture_ids = extract_fixture_ids(html, INICIADOS_A)
        self.assertEqual(len(fixture_ids), 14)
        self.assertEqual(fixture_ids[:3], ['640944', '640945', '640946'])
        self.assertEqual(fixture_ids[-1], '640957')

    def test_real_main_page_uses_first_block_fallback_for_feminino_sub15(self):
        html = self.read_fixture('competition_feminino_sub15_main.html')
        fixture_ids = extract_fixture_ids(html, FEMININO_SUB15)
        self.assertEqual(len(fixture_ids), 14)
        self.assertEqual(fixture_ids[:3], ['626066', '626067', '626068'])
        self.assertEqual(fixture_ids[-1], '626079')

    def test_real_fixture_parses_infantis_a_matches_and_classification(self):
        fragment = self.read_fixture('fixture_infantis_a_626094.html')
        matches = parse_matches(fragment)
        classification = parse_classification(fragment)

        self.assertEqual(len(matches), 5)
        self.assertEqual(len(classification), 10)

        first_match = matches[0]
        self.assertEqual(first_match['home'], 'Nucleo Sporting C.P. Olhão')
        self.assertEqual(first_match['away'], 'Js Campinense')
        self.assertEqual(first_match['homeScore'], 4)
        self.assertEqual(first_match['awayScore'], 2)

        first_entry = classification[0]
        self.assertEqual(first_entry['team'], 'Cf Os Armacenenses')
        self.assertEqual(first_entry['position'], 1)
        self.assertEqual(first_entry['points'], 34)

    def test_real_fixture_parses_benjamins_a1_matches_without_classification(self):
        fragment = self.read_fixture('fixture_benjamins_a1_641124.html')
        matches = parse_matches(fragment, strip_score_from_date=True)
        classification = parse_classification(fragment)

        self.assertEqual(len(matches), 3)
        self.assertEqual(len(classification), 0)

        first_match = matches[0]
        self.assertEqual(first_match['home'], 'Jc Aljezurense')
        self.assertEqual(first_match['away'], 'Portimonense Sc')
        self.assertEqual(first_match['date'], '28 fev')
        self.assertEqual(first_match['homeScore'], 3)
        self.assertEqual(first_match['awayScore'], 6)

    def test_parse_zerozero_round_results(self):
        html = '''
        <div id="fixture_games" class="box_container">
            <table class="zztable stats">
                <tbody>
                    <tr>
                        <td>10/05</td>
                        <td class="text"><a>Olhanense</a></td>
                        <td><img alt="Olhanense"></td>
                        <td class="result"><a>1-1</a></td>
                        <td><img alt="Ferreiras"></td>
                        <td class="text"><a>Ferreiras</a></td>
                    </tr>
                    <tr>
                        <td>&nbsp;</td>
                        <td class="text"><a>Sambrasense</a></td>
                        <td><img alt="Sambrasense"></td>
                        <td class="result"><a>2-0</a></td>
                        <td><img alt="Odiáxere"></td>
                        <td class="text"><a>Odiáxere</a></td>
                    </tr>
                </tbody>
            </table>
        </div>
        '''
        results = parse_zerozero_round_results(html)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['home'], 'Olhanense')
        self.assertEqual(results[0]['away'], 'Ferreiras')
        self.assertEqual(results[0]['homeScore'], 1)
        self.assertEqual(results[0]['awayScore'], 1)

    def test_fill_missing_scores_from_secondary_results(self):
        rounds = [
            {
                'index': 15,
                'matches': [
                    {
                        'home': 'Sc Olhanense',
                        'away': 'Fc Ferreiras',
                        'date': '10 mai',
                        'time': '16:00',
                        'stadium': 'Estádio José Arcanjo',
                        'homeScore': None,
                        'awayScore': None,
                    },
                    {
                        'home': 'Udr Sambrasense',
                        'away': 'Cd Odiáxere',
                        'date': '10 mai',
                        'time': '16:00',
                        'stadium': 'Campo Polidesportivo',
                        'homeScore': None,
                        'awayScore': None,
                    },
                ],
                'classification': [],
            }
        ]
        config = CompetitionConfig(
            competition_url='https://example.test',
            output_file='data/example.json',
            main_cache_key='example_main',
            fixture_cache_prefix='example_fixture',
            secondary_results_url='https://zerozero.example/edition',
            secondary_results_phase_id='232614',
            secondary_results_team_aliases={
                'Sc Olhanense': 'Olhanense',
                'Fc Ferreiras': 'Ferreiras',
                'Udr Sambrasense': 'Sambrasense',
                'Cd Odiáxere': 'Odiáxere',
            },
        )

        def fake_fetcher(_url):
            return '''
            <div id="fixture_games" class="box_container">
                <table class="zztable stats">
                    <tbody>
                        <tr>
                            <td>10/05</td>
                            <td class="text"><a>Olhanense</a></td>
                            <td><img alt="Olhanense"></td>
                            <td class="result"><a>1-1</a></td>
                            <td><img alt="Ferreiras"></td>
                            <td class="text"><a>Ferreiras</a></td>
                        </tr>
                        <tr>
                            <td>&nbsp;</td>
                            <td class="text"><a>Sambrasense</a></td>
                            <td><img alt="Sambrasense"></td>
                            <td class="result"><a>2-0</a></td>
                            <td><img alt="Odiáxere"></td>
                            <td class="text"><a>Odiáxere</a></td>
                        </tr>
                    </tbody>
                </table>
            </div>
            '''

        filled = fill_missing_scores_from_secondary_results(
            rounds,
            config,
            today=datetime(2026, 5, 11, 12, 0, 0),
            page_fetcher=fake_fetcher,
        )

        self.assertEqual(filled, 2)
        self.assertEqual(rounds[0]['matches'][0]['homeScore'], 1)
        self.assertEqual(rounds[0]['matches'][0]['awayScore'], 1)
        self.assertEqual(rounds[0]['matches'][1]['homeScore'], 2)
        self.assertEqual(rounds[0]['matches'][1]['awayScore'], 0)


if __name__ == '__main__':
    unittest.main()
