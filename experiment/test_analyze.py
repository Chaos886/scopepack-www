"""Artificial score fixtures test statistics only, never model performance."""
import copy
import unittest
from analyze import analyze


def records():
    result = []
    # Each cluster includes two related questions; preserve pairing on resample.
    for i, (c, b, f) in enumerate([(1, 0, 1), (0, 1, 1), (1, 0, 0), (1, 1, 0)]):
        for method, budget, answer in [('closure', 64, c), ('bm25', 64, b), ('full', 0, f)]:
            result.append(dict(id=f'{i}:{method}', sample_id=f'q{i}', cluster_id=f'c{i//2}',
                               method=method, budget=budget, answer_em=answer,
                               joint_exact_evidence=answer, valid=1, missing=0))
    return result


class PairedAnalysisTests(unittest.TestCase):
    def test_known_transitions_and_difference(self):
        report = analyze(records(), budget=64, resamples=100)
        self.assertEqual(report['n_clusters'], 2)
        self.assertEqual(report['metrics']['answer_em']['difference_pp'], 25)
        self.assertEqual(report['damage_pct'], 50)
        self.assertEqual(report['rescue_pct'], 100)

    def test_whole_clusters_are_resampled(self):
        # Both questions in each cluster change together, so bootstrap endpoints
        # are exactly the two cluster-level differences, 0 and 50 pp.
        report = analyze(records(), budget=64, resamples=1000, seed=7)
        self.assertEqual(report['metrics']['answer_em']['cluster_bootstrap_95ci_pp'], [0, 50])
        self.assertEqual(report, analyze(records(), budget=64, resamples=1000, seed=7))

    def test_missing_predictions_are_counted(self):
        rows = records()
        rows[0].update(missing=1, valid=0, answer_em=0, joint_exact_evidence=0)
        report = analyze(rows, budget=64, resamples=100)
        self.assertEqual(report['n_questions'], 4)
        self.assertEqual(report['missing_pct']['candidate'], 25)
        self.assertEqual(report['metrics']['answer_em']['candidate_pct'], 50)

    def test_unpaired_duplicate_and_cluster_mismatch_rejected(self):
        for changed in ('unpaired', 'duplicate', 'cluster'):
            rows = records()
            if changed == 'unpaired': rows.pop()
            if changed == 'duplicate': rows.append(copy.deepcopy(rows[0]))
            if changed == 'cluster': rows[0]['cluster_id'] = 'wrong'
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                analyze(rows, budget=64, resamples=100)

    def test_undefined_denominators_and_one_cluster(self):
        rows = records()
        for row in rows:
            row['cluster_id'] = 'one-cluster'
            if row['method'] == 'full':
                row.update(answer_em=0, joint_exact_evidence=0)
        report = analyze(rows, budget=64, resamples=100)
        self.assertIsNone(report['damage_pct'])
        self.assertIsNone(report['metrics']['answer_em']['cluster_bootstrap_95ci_pp'])

    def test_impossible_scores_rejected(self):
        rows = records()
        rows[0].update(missing=1)
        with self.assertRaises(ValueError):
            analyze(rows, budget=64, resamples=100)


if __name__ == '__main__':
    unittest.main()
