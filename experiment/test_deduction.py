"""Independent logical cases and pipeline tests; never claim LLM performance."""
import copy
from pathlib import Path
import random
import unittest
import uuid

from deduction import (build_report, classify, inventory, make_suite, score_deduction,
                       solve, validate_program, VERSION)
from prototype import (CounterUnits, digest, evaluate, prepare, public_input, read_jsonl,
                       score_one, select, write_jsonl)
from run_local import verify_requests
from validate_data import validate_dataset


def fact(cid, literal):
    return {'id': cid, 'kind': 'fact', 'literal': literal}


def rule(cid, premises, conclusion):
    return {'id': cid, 'kind': 'rule', 'premises': premises, 'conclusion': conclusion}


class DeductionTests(unittest.TestCase):
    def setUp(self):
        self.samples = make_suite(families=1, depths=(0, 1, 2, 4))
        self.scratch = Path(__file__).resolve().parents[1] / 'work' / 'unit-tests' / uuid.uuid4().hex
        self.scratch.mkdir(parents=True)

    def test_conjunction_and_depth_are_not_path_length_or_fact_count(self):
        clauses = [fact('a', 'a'), fact('b', 'b'), rule('r1', ['a', 'b'], 'c'), rule('r2', ['c'], 'd')]
        proofs, depths = solve(clauses)
        self.assertEqual(proofs['d'], {frozenset(['a', 'b', 'r1', 'r2'])})
        self.assertEqual(depths['d'], 2)
        selected, _ = solve(clauses, {'a', 'r1', 'r2'})
        self.assertEqual(classify(selected, 'd'), 'unknown')

    def test_no_converse_no_contraposition_and_no_negation_by_absence(self):
        for clauses in ([fact('b', 'b'), rule('r', ['a'], 'b')],
                        [fact('nb', '!b'), rule('r', ['a'], 'b')],
                        [fact('x', 'x')]):
            self.assertEqual(classify(solve(clauses)[0], 'a'), 'unknown')
        self.assertEqual(classify(solve([fact('na', '!a')])[0], 'a'), 'contradicted')

    def test_explicit_negative_premise_requires_a_fact_or_derivation(self):
        clauses = [rule('r', ['!a'], 'b')]
        self.assertEqual(classify(solve(clauses)[0], 'b'), 'unknown')
        clauses.append(fact('na', '!a'))
        self.assertEqual(classify(solve(clauses)[0], 'b'), 'entailed')

    def test_cycles_need_a_grounded_base_and_supports_stay_minimal(self):
        clauses = [rule('r1', ['a'], 'b'), rule('r2', ['b'], 'a')]
        self.assertEqual(classify(solve(clauses)[0], 'b'), 'unknown')
        clauses.append(fact('f', 'a'))
        proofs, depths = solve(clauses)
        self.assertEqual(proofs['a'], {frozenset(['f'])})
        self.assertEqual(proofs['b'], {frozenset(['f', 'r1'])})
        self.assertEqual(depths['b'], 1)

    def test_all_alternative_supports_and_shortest_depth(self):
        clauses = [fact('f1', 'a'), fact('f2', 'b'), rule('r1', ['a'], 'c'),
                   rule('r2', ['b'], 'x'), rule('r3', ['x'], 'c')]
        proofs, depths = solve(clauses)
        self.assertEqual(proofs['c'], {frozenset(['f1', 'r1']), frozenset(['f2', 'r2', 'r3'])})
        self.assertEqual(depths['c'], 1)
        with self.assertRaisesRegex(ValueError, 'cap exceeded'):
            solve(clauses, max_proofs=1)

    def test_independent_reachability_reference_on_small_random_programs(self):
        # Deliberately simpler oracle has no provenance/depth code in common.
        rng = random.Random(19)
        atoms = ['a', '!a', 'b', '!b', 'c', '!c']
        for trial in range(60):
            clauses = [fact(f'f{i}', a) for i, a in enumerate(rng.sample(atoms, rng.randrange(4)))]
            for i in range(8):
                clauses.append(rule(f'r{i}', rng.sample(atoms, rng.randint(1, 2)), rng.choice(atoms)))
            known = {c['literal'] for c in clauses if c['kind'] == 'fact'}
            while True:
                expanded = known | {c['conclusion'] for c in clauses if c['kind'] == 'rule' and set(c['premises']) <= known}
                if expanded == known:
                    break
                known = expanded
            proofs, _ = solve(clauses)
            self.assertEqual({a for a, s in proofs.items() if s}, known, trial)
            for atom, supports in proofs.items():
                for support in supports:
                    self.assertTrue(solve(clauses, support)[0].get(atom))
                    for cid in support:
                        self.assertFalse(solve(clauses, support - {cid})[0].get(atom))

    def test_generated_inventory_gold_and_reproducibility(self):
        full = make_suite()
        info = inventory(full)
        self.assertEqual(info['samples'], 60)
        self.assertEqual(info['labels'], {'entailed': 20, 'contradicted': 20, 'unknown': 20})
        self.assertEqual(full, make_suite())
        for sample in full:
            result = validate_program(sample)
            if result['label'] != 'unknown':
                self.assertEqual(result['proof_depth'], sample['deduction']['template_depth'])
        self.assertTrue(all(s['split'] == 'dev' for s in full))

    def test_metadata_and_public_text_mismatch_rejected(self):
        for modify in (
            lambda s: s['deduction'].update(label='contradicted'),
            lambda s: s['deduction'].update(proof_depth=99),
            lambda s: s['documents'][0]['sentences'][0].update(text='Tampered text.'),
            lambda s: s.update(question='A different query'),
            lambda s: s['gold'].update(evidence_sets=[['D1:s1']]),
        ):
            sample = copy.deepcopy(self.samples[3])
            modify(sample)
            with self.subTest(modify=modify), self.assertRaises(ValueError):
                validate_dataset([sample])

    def test_logic_annotations_do_not_enter_selection_or_messages(self):
        sample = self.samples[-3]
        changed = copy.deepcopy(sample)
        changed['deduction'] = {'label': 'LEAK_SENTINEL', 'clauses': ['GOLD_SENTINEL']}
        changed['gold'] = {'answers': ['GOLD_SENTINEL']}
        self.assertEqual(public_input(sample), public_input(changed))
        self.assertEqual(select(public_input(sample), 'closure', 256, CounterUnits()),
                         select(public_input(changed), 'closure', 256, CounterUnits()))
        self.assertNotIn('deduction', public_input(sample))

    def test_citation_sufficiency_allows_extra_visible_evidence(self):
        sample = self.samples[-3]
        ids = {c['id'] for c in sample['deduction']['clauses']}
        output = {'answer': 'entailed', 'citations': sorted(ids), 'abstain': False}
        base = score_one(sample['gold'], output, ids)
        result = score_deduction(sample, output, ids, base)
        self.assertEqual(base['joint_exact_evidence'], 0)  # Extra citations fail old exact-set proxy.
        self.assertEqual(result['proof_supported_correct'], 1)  # But the formal proof is sufficient.
        output['citations'] = []
        result = score_deduction(sample, output, ids, score_one(sample['gold'], output, ids))
        self.assertEqual(result['logic_label_correct'], 1)
        self.assertEqual(result['proof_supported_correct'], 0)

    def test_compression_refusal_is_separate_from_full_task_success(self):
        sample = self.samples[-3]
        output = {'answer': '', 'citations': [], 'abstain': True}
        result = score_deduction(sample, output, [], score_one(sample['gold'], output, set()))
        self.assertEqual(result['proof_retained'], 0)
        self.assertEqual(result['logic_label_correct'], 0)
        self.assertEqual(result['visible_label_correct'], 1)
        unknown = self.samples[-1]
        result = score_deduction(unknown, output, [], score_one(unknown['gold'], output, set()))
        self.assertEqual(result['logic_label_correct'], 1)
        self.assertIsNone(result['proof_retained'])
        self.assertIsNone(result['proof_supported_correct'])

    def test_end_to_end_preparation_scoring_missing_pairs_and_runner(self):
        data = self.scratch / 'data.jsonl'
        write_jsonl(data, self.samples)
        out = self.scratch / 'prepared'
        prepare(data, out, ['full', 'none', 'bm25', 'closure'], [128])
        requests = read_jsonl(out / 'requests.jsonl')
        class CounterBackend:
            def count_text(self, text):
                return CounterUnits()(text)
        verify_requests(requests, self.samples, CounterBackend(), True)
        # Constructed outputs are SOFTWARE TESTS only; no fake research score is saved in the repo.
        samples = {s['id']: s for s in self.samples}
        predictions = []
        for request in requests:
            sample = samples[request['sample_id']]
            if request['method'] != 'full':
                continue  # Missing predictions remain in the planned denominator.
            gold = sample['gold']
            output = {'answer': gold['answers'][0] if gold['answers'] else '',
                      'citations': gold['evidence_sets'][0] if gold['evidence_sets'] else [],
                      'abstain': gold['abstain']}
            predictions.append({'id': request['id'], 'request_sha256': digest(request), 'output': output})
        pred_path = self.scratch / 'test_predictions.jsonl'
        write_jsonl(pred_path, predictions)
        evaluate(data, out / 'requests.jsonl', pred_path, self.scratch / 'eval')
        rows = read_jsonl(self.scratch / 'eval/scores.jsonl')
        report = build_report(rows)
        full = next(g for g in report['groups'] if g['method'] == 'full')
        self.assertEqual(full['all_three_worlds_correct_pct'], 100)
        self.assertEqual(full['complete_world_triplets'], 4)
        none = next(g for g in report['groups'] if g['method'] == 'none')
        self.assertEqual(none['missing_n'], len(self.samples))
        self.assertEqual(none['answer_accuracy_pct'], 0)
        self.assertIsNone(none['answer_accuracy_given_proof_retained_pct'])
        incomplete = build_report(rows[:1])['groups'][0]
        self.assertEqual(incomplete['incomplete_world_triplets'], 1)
        self.assertIsNone(incomplete['all_three_worlds_correct_pct'])
        self.assertIsNone(incomplete['macro_three_label_accuracy_pct'])
        broken = copy.deepcopy(rows)
        broken[0]['logic_label_correct'] = 1 - broken[0]['logic_label_correct']
        with self.assertRaises(ValueError):
            build_report(broken)
        altered_requests = copy.deepcopy(requests)
        altered_requests[0]['selected_ids'] = []
        bad_request_path = self.scratch / 'tampered_requests.jsonl'
        write_jsonl(bad_request_path, altered_requests)
        with self.assertRaisesRegex(ValueError, 'Invalid full-context reference'):
            evaluate(data, bad_request_path, pred_path, self.scratch / 'should_not_score')


if __name__ == '__main__':
    unittest.main()
