"""验证期间视图、供给安排比较和方案保留审议链。"""
import json
import unittest
from pathlib import Path

from climate_analysis.evidence import connect, receive
from climate_analysis.network import view
from climate_analysis.allocation import evaluate
from climate_analysis.plan import propose, review

DATA = json.loads((Path(__file__).resolve().parents[1] / 'data/planning_example.json').read_text(encoding='utf8'))
T1, T2 = DATA['known_at']


class Planning(unittest.TestCase):
    def setUp(self):
        self.db = connect(':memory:')
        for doc in DATA['documents']:
            receive(self.db, doc)
        self.before = view(self.db, T1, DATA['period'])
        self.after = view(self.db, T2, DATA['period'])

    def tearDown(self):
        self.db.close()

    def test_period_filter(self):
        excluded = {(e['id'], e['kind']) for e in self.before['excluded']}
        self.assertIn(('anom-A-old', 'anomaly'), excluded)
        self.assertEqual(self.before['districts']['district-A']['anomaly']['id'], 'anom-A')

    def test_backup_plant_covers_anomaly(self):
        table = evaluate(self.before)
        self.assertEqual(table['本地常规']['districts']['district-A']['gap'], 4)
        self.assertEqual(table['本地全部']['districts']['district-A']['gap'], 0)

    def test_transfer_reduces_gap(self):
        table = evaluate(self.before)
        self.assertEqual(table['本地全部']['districts']['district-B']['gap'], 4)
        self.assertEqual(table['本地全部+调水']['districts']['district-B']['gap'], 1)
        self.assertEqual(table['本地全部+调水']['flows'],
                         [{'line': 'line-T1', 'from': 'district-C',
                           'to': 'district-B', 'amount': 3}])

    def test_affected_population_partial_tier(self):
        row = evaluate(self.before)['本地全部+调水']['districts']['district-B']
        self.assertEqual(row['curtailment'][0]['level'], 3)
        self.assertEqual(row['affected_population'], 3333)

    def test_plan_kept_and_re_review(self):
        plan = propose(self.before, '本地全部+调水')
        result = review(plan, self.before, self.after)
        self.assertEqual(result['kept_plan'], plan)
        flagged = {item['district']: item for item in result['re_review']}
        self.assertEqual(set(flagged), {'district-A', 'district-B', 'district-C'})
        self.assertEqual(result['unchanged'], ['district-D'])
        a_kinds = {r['kind'] for r in flagged['district-A']['reasons']}
        self.assertEqual(a_kinds, {'证据变化'})
        b_kinds = {r['kind'] for r in flagged['district-B']['reasons']}
        self.assertEqual(b_kinds, {'证据变化', '能力变化'})
        self.assertTrue(flagged['district-B']['capability_changed'])
        self.assertEqual(flagged['district-B']['gap_if_recomputed'], 4)
        self.assertEqual(flagged['district-A']['gap_if_recomputed'], 0.5)

    def test_plan_immune_to_later_documents(self):
        plan = propose(self.before, '本地全部+调水')
        again = propose(view(self.db, T1, DATA['period']), '本地全部+调水')
        self.assertEqual(plan['fingerprint'], again['fingerprint'])
        self.assertIsNone(self.after['districts']['district-B']['anomaly']['payload']['value'])


if __name__ == '__main__':
    unittest.main()
