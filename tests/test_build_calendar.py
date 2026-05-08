import unittest
from datetime import datetime

from build_calendar import build_calendar_entries, build_match_datetime, clean_display_date
from competition_configs import CompetitionConfig


class BuildCalendarTests(unittest.TestCase):
    def setUp(self):
        self.config = CompetitionConfig(
            competition_url='https://example.test',
            output_file='data/example.json',
            main_cache_key='example_main',
            fixture_cache_prefix='example_fixture',
            club_team_names=frozenset({'Casa FC'}),
            key='example-key',
            title='Competição Exemplo',
            subtitle='Fase Exemplo',
            page_path='example.html',
        )

    def test_clean_display_date_removes_embedded_score(self):
        self.assertEqual(clean_display_date('2 - 1 3 mai'), '3 mai')

    def test_build_match_datetime_uses_time_when_available(self):
        result = build_match_datetime({
            'date': '3 mai',
            'time': '11:30',
        })
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 5)
        self.assertEqual(result.day, 3)
        self.assertEqual(result.hour, 11)
        self.assertEqual(result.minute, 30)

    def test_build_calendar_entries_assigns_status_and_metadata(self):
        payload = {
            'lastUpdatedAt': '2026-05-08T18:18:11Z',
            'sourceHealth': {'status': 'ok', 'fallbackReuseCount': 0},
            'rounds': [
                {
                    'index': 9,
                    'fixtureId': '12345',
                    'matches': [
                        {
                            'home': 'Casa FC',
                            'away': 'Fora FC',
                            'date': '5 - 2 3 mai',
                            'time': '',
                            'stadium': 'Campo A',
                            'homeScore': 5,
                            'awayScore': 2,
                        },
                        {
                            'home': 'Casa B',
                            'away': 'Fora B',
                            'date': '10 mai',
                            'time': '11:00',
                            'stadium': 'Campo B',
                            'homeScore': None,
                            'awayScore': None,
                        },
                        {
                            'home': 'Outra Casa',
                            'away': 'Outra Fora',
                            'date': '11 mai',
                            'time': '09:00',
                            'stadium': 'Campo C',
                            'homeScore': None,
                            'awayScore': None,
                        },
                    ],
                    'classification': [],
                }
            ],
        }

        entries = build_calendar_entries(
            self.config,
            payload,
            now=datetime(2026, 5, 8, 12, 0, 0).astimezone(),
        )

        self.assertEqual(len(entries), 1)

        finished = entries[0]
        self.assertEqual(finished['status'], 'finished')
        self.assertEqual(finished['displayDate'], '3 mai')
        self.assertEqual(finished['competitionKey'], 'example-key')
        self.assertEqual(finished['competitionUrl'], 'example.html#resultados-j9')

    def test_build_calendar_entries_accepts_multiple_club_team_names(self):
        config = CompetitionConfig(
            competition_url='https://example.test',
            output_file='data/example.json',
            main_cache_key='example_main',
            fixture_cache_prefix='example_fixture',
            club_team_names=frozenset({'Casa FC - A', 'Casa FC - B'}),
            key='example-key',
            title='Competição Exemplo',
            subtitle='Fase Exemplo',
            page_path='example.html',
        )
        payload = {
            'lastUpdatedAt': '2026-05-08T18:18:11Z',
            'sourceHealth': {'status': 'ok', 'fallbackReuseCount': 0},
            'rounds': [
                {
                    'index': 9,
                    'fixtureId': '12345',
                    'matches': [
                        {
                            'home': 'Casa FC - A',
                            'away': 'Fora FC',
                            'date': '6 - 0 3 mai',
                            'time': '',
                            'stadium': 'Campo A',
                            'homeScore': 6,
                            'awayScore': 0,
                        },
                        {
                            'home': 'Outra Casa',
                            'away': 'Casa FC - B',
                            'date': '4 - 1 3 mai',
                            'time': '',
                            'stadium': 'Campo B',
                            'homeScore': 4,
                            'awayScore': 1,
                        },
                    ],
                }
            ],
        }

        entries = build_calendar_entries(
            config,
            payload,
            now=datetime(2026, 5, 8, 12, 0, 0).astimezone(),
        )

        self.assertEqual(len(entries), 2)


if __name__ == '__main__':
    unittest.main()
