import json
import unittest
from pathlib import Path
from benchmark.evaluation_history import build_history

ROOT = Path(__file__).resolve().parents[1]


class EvaluationHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = build_history(ROOT)

    def test_scores_match_saved_trials(self):
        for version, filename in [('baseline', 'benchmark-results.json'),
                                  ('repair', 'repair-final-results.json')]:
            data = json.loads((ROOT / 'benchmark' / filename).read_text())
            first = [r for r in data['results'] if r['core'] and r['mode'] == 'online'
                     and r['repeat'] == 1]
            score = self.history[version]['summary']['online']['pass_k'][0]
            self.assertEqual(score['eligible'], len(first))
            self.assertEqual(score['passed'], sum(r['status'] == 'PASS' for r in first))

    def test_failure_and_replacement_probe_remain_separate(self):
        row = next(e for e in self.history['examples'] if e['id'] == 'U060')
        self.assertEqual(row['repair']['status'], 'FAIL')
        self.assertTrue(any(not c['passed'] for c in row['repair']['checks']))
        self.assertEqual(self.history['timeout_probe']['id'], 'U060-R1')
        self.assertEqual(self.history['timeout_probe']['status'], 'PASS')
        self.assertTrue(all(p['rate'] is None for p in
                            self.history['repair']['summary']['online']['pass_k'][1:]))

    def test_redblue_versions_keep_original_failure_and_turn_counts(self):
        samples = self.history['redblue']
        self.assertEqual([s['trace']['final_verdict']['status'] for s in samples],
                         ['FAIL', 'PASS', 'PASS'])
        self.assertEqual([len(s['trace']['turns']) for s in samples], [2, 1, 2])
        self.assertEqual(len({s['run_id'] for s in samples}), 3)

    def test_early_suite_and_semantic_metrics_not_relabelled(self):
        self.assertEqual(self.history['early']['counts']['PASS'], 56)
        self.assertEqual(self.history['early']['blocked'], ['U028'])
        unsupported = next(m for m in self.history['metrics']
                           if m['mode'] == 'online' and m['id'] == 'unsupported_answer')
        self.assertEqual((unsupported['numerator'], unsupported['denominator']), (41, 101))


if __name__ == '__main__':
    unittest.main()
