"""Protect experiment identity, denominators and prior files; no real model calls."""
import copy
import json
from pathlib import Path
import unittest
import uuid

from prototype import (CounterUnits, digest, evaluate, prepare, public_input,
                       read_jsonl, select, write_jsonl)
from validate_data import file_sha256


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1] / 'work' / 'unit-tests' / uuid.uuid4().hex
        self.root.mkdir(parents=True)
        self.data = Path(__file__).with_name('demo.jsonl')
        self.prepared = self.root / 'prepared'
        prepare(self.data, self.prepared, ['full', 'none'], [64])
        self.requests = self.prepared / 'requests.jsonl'
        self.predictions = self.root / 'predictions.jsonl'
        write_jsonl(self.predictions, [])

    def test_prepare_and_evaluate_preserve_existing_artifacts(self):
        original = self.requests.read_bytes()
        with self.assertRaises(FileExistsError):
            prepare(self.data, self.prepared, ['full'], [32])
        self.assertEqual(self.requests.read_bytes(), original)
        evaluate(self.data, self.requests, self.predictions, self.prepared)
        before = {p.name: p.read_bytes() for p in self.prepared.iterdir() if p.is_file()}
        with self.assertRaises(FileExistsError):
            evaluate(self.data, self.requests, self.predictions, self.prepared)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.prepared.iterdir() if p.is_file()})

    def test_partial_output_and_input_file_as_output_are_protected(self):
        out = self.root / 'partial'
        out.mkdir()
        existing = out / 'summary.json'
        existing.write_text('preserve incomplete run', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            evaluate(self.data, self.requests, self.predictions, out)
        self.assertFalse((out / 'scores.jsonl').exists())
        with self.assertRaises(FileExistsError):
            prepare(self.data, self.requests, ['full'], [64])

    def test_invalid_or_duplicate_matrix_rejected_before_writing(self):
        for methods, budgets in [([], [64]), (['full', 'full'], [64]), (['invented'], [64]),
                                 (['bm25'], []), (['bm25'], [64, 64]), (['bm25'], [-1]),
                                 (['bm25'], [True])]:
            out = self.root / 'invalid'
            with self.subTest(methods=methods, budgets=budgets), self.assertRaises(ValueError):
                prepare(self.data, out, methods, budgets)
            self.assertFalse(out.exists())

    def test_duplicate_cells_empty_and_mixed_units_rejected(self):
        rows = read_jsonl(self.requests)
        duplicate = copy.deepcopy(rows)
        duplicate.append(dict(rows[0], id='different_id_same_cell'))
        mixed = copy.deepcopy(rows)
        mixed[0]['budget_unit'] = 'target_tokenizer'
        for requests in ([], duplicate, mixed):
            path = self.root / 'bad_requests.jsonl'
            write_jsonl(path, requests)
            with self.assertRaises(ValueError):
                evaluate(self.data, path, self.predictions, self.root / 'bad_evaluation')

    def test_mixed_or_partially_missing_run_ids_rejected(self):
        rows = read_jsonl(self.requests)
        for predictions in ([{'id': rows[0]['id'], 'run_id': 'runA'}, {'id': rows[1]['id'], 'run_id': 'runB'}],
                            [{'id': rows[0]['id'], 'run_id': 'runA'}, {'id': rows[1]['id']}],
                            [{'id': rows[0]['id'], 'run_id': ''}]):
            write_jsonl(self.predictions, predictions)
            with self.assertRaisesRegex(ValueError, 'run_id'):
                evaluate(self.data, self.requests, self.predictions, self.root / 'mixed')

    def test_manifest_binds_inputs_code_output_and_missing_count(self):
        rows = read_jsonl(self.requests)
        write_jsonl(self.predictions, [{'id': rows[0]['id'], 'run_id': 'software_test_only',
                                       'request_sha256': digest(rows[0]), 'output': None}])
        out = self.root / 'evaluation'
        evaluate(self.data, self.requests, self.predictions, out)
        manifest = json.loads((out / 'evaluation_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['prediction_run_id'], 'software_test_only')
        self.assertEqual(manifest['missing_predictions'], len(rows) - 1)
        self.assertEqual(manifest['scores_sha256'], file_sha256(out / 'scores.jsonl'))
        self.assertEqual(manifest['dataset_sha256'], file_sha256(self.data))
        self.assertEqual(manifest['predictions_sha256'], file_sha256(self.predictions))
        self.assertTrue(manifest['prediction_request_hashes_complete'])

    def test_selection_cache_counts_each_rendered_subset_once(self):
        sample = read_jsonl(self.data)[0]
        for method in ('head', 'bm25', 'neighbors', 'closure'):
            measured = []
            def count(text):
                measured.append(text)
                return CounterUnits()(text)
            actual = select(public_input(sample), method, 128, count)
            expected = select(public_input(sample), method, 128, CounterUnits())
            self.assertEqual(actual, expected)
            self.assertEqual(len(measured), len(set(measured)))


if __name__ == '__main__':
    unittest.main()
