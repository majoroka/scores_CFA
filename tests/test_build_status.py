import unittest

from build_status import build_competition_status
from competition_configs import SENIORES


class BuildStatusTests(unittest.TestCase):
    def test_build_competition_status_uses_payload_quality(self):
        payload = {
            'lastUpdatedAt': '2026-05-10T21:11:55Z',
            'sourceHealth': {
                'status': 'partial',
                'fallbackReuseCount': 0,
                'issues': ['pending scores'],
            },
            'dataQuality': {
                'roundCount': 3,
                'matchCount': 9,
                'completedMatchCount': 7,
                'matchesWithoutScore': 2,
                'pastMatchesWithoutScore': 1,
                'teamCount': 10,
                'roundsWithCompletedMatches': 2,
            },
            'rounds': [],
        }
        status = build_competition_status(SENIORES, payload)
        self.assertEqual(status['status'], 'partial')
        self.assertEqual(status['fallbackReuseCount'], 0)
        self.assertEqual(status['matchesWithoutScore'], 2)
        self.assertEqual(status['pastMatchesWithoutScore'], 1)
        self.assertEqual(status['roundCount'], 3)
        self.assertEqual(status['teamCount'], 10)
        self.assertEqual(status['issues'], ['pending scores'])


if __name__ == '__main__':
    unittest.main()
