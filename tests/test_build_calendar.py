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

        self.assertEqual(len(entries), 2)

        finished, scheduled = entries
        self.assertEqual(finished['status'], 'finished')
        self.assertEqual(finished['displayDate'], '3 mai')
        self.assertEqual(finished['competitionKey'], 'example-key')
        self.assertEqual(finished['competitionUrl'], 'example.html#resultados-j9')

        self.assertEqual(scheduled['status'], 'scheduled')
        self.assertEqual(scheduled['displayTime'], '11:00')
        self.assertTrue(scheduled['matchDateISO'].startswith('2026-05-10T11:00:00'))


if __name__ == '__main__':
    unittest.main()
