import unittest
from datetime import datetime

from competition_configs import CompetitionConfig
from competition_sync import (
    build_payload,
    compute_default_round_index,
    extract_fixture_ids,
    parse_classification,
    parse_match_date,
    parse_matches,
)


class CompetitionSyncTests(unittest.TestCase):
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
        self.assertEqual(payload['rounds'], rounds)


if __name__ == '__main__':
    unittest.main()
