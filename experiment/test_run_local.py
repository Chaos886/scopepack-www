"""Fake backend checks infrastructure only. No real model performance is measured."""
import copy
from pathlib import Path
import unittest
import uuid

from prototype import digest, evaluate, prepare, read_jsonl, write_jsonl
from run_local import parse_output, run_batch, verify_requests


class FakeBackend:
    metadata = {'adapter': 'FAKE_SOFTWARE_TEST_NOT_MODEL_INFERENCE'}
    runtime = {'test_only': True}

    def __init__(self, replies=None, interrupt=False):
        self.replies = replies or ['{"answer":"","citations":[],"abstain":true}']
        self.calls = 0
        self.loads = 0
        self.interrupt = interrupt

    def count_text(self, text):
        return len(text)

    def encode(self, messages):
        if messages[0]['content'] == 'TEMPLATE_ERROR':
            raise ValueError('Unsupported template')
        return [1] * int(messages[0]['content'])

    def load(self):
        self.loads += 1

    def generate(self, tokens):
        self.calls += 1
        if self.interrupt:
            raise KeyboardInterrupt()
        result = self.replies[(self.calls - 1) % len(self.replies)]
        if isinstance(result, Exception):
            raise result
        return {'raw_text': result, 'generated_token_ids': [9], 'output_tokens': 1,
                'generation_ms': 0.0, 'finish_reason': 'test_only'}


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1] / 'work' / 'unit-tests' / uuid.uuid4().hex
        self.root.mkdir(parents=True)
        self.data = Path(__file__).with_name('demo.jsonl')

    def requests(self, *sizes):
        return [{'id': str(i), 'messages': [{'role': 'user', 'content': str(size)}]}
                for i, size in enumerate(sizes)]

    def run_fake(self, requests, backend, **kwargs):
        return run_batch(requests, backend, self.root / 'run', {'test_only': True}, 20, 5, **kwargs)

    def test_exact_json_no_repair(self):
        valid = '{"answer":"No","citations":["D1:s1"],"abstain":false}'
        self.assertEqual(parse_output(valid)['answer'], 'No')
        for bad in ('```json\n' + valid + '\n```', valid + valid,
                    '{"answer":"No","citations":[],"abstain":"false"}',
                    '{"answer":"No","answer":"Yes","citations":[],"abstain":false}',
                    '{"answer":"No","citations":[],"abstain":false,"extra":0}'):
            self.assertIsNone(parse_output(bad))

    def test_preflight_never_generates_or_loads(self):
        backend = FakeBackend()
        result = self.run_fake(self.requests(15, 16, 'TEMPLATE_ERROR'), backend, preflight_only=True)
        self.assertEqual(result['counts'], {'ready': 1, 'context_overflow': 1, 'template_error': 1})
        self.assertEqual((backend.loads, backend.calls), (0, 0))
        self.assertFalse((self.root / 'run' / 'predictions.jsonl').exists())

    def test_failures_retained_and_raw_output_preserved(self):
        backend = FakeBackend(['not JSON', RuntimeError('test generation failure')])
        result = self.run_fake(self.requests(15, 3, 16, 'TEMPLATE_ERROR'), backend)
        self.assertEqual(result['counts'], {'context_overflow': 1, 'template_error': 1,
                                          'invalid_output': 1, 'generation_error': 1})
        rows = read_jsonl(self.root / 'run' / 'predictions.jsonl')
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]['raw_text'], 'not JSON')
        self.assertTrue(all(r['output'] is None for r in rows))
        self.assertEqual(backend.calls, 2)

    def test_resume_no_duplicate_generation_and_changed_identity_rejected(self):
        backend = FakeBackend()
        requests = self.requests(3, 4)
        first = self.run_fake(requests, backend)
        second = self.run_fake(requests, backend, resume=True)
        self.assertEqual(first['run_id'], second['run_id'])
        self.assertEqual(backend.calls, 2)
        requests[0]['messages'][0]['content'] = '5'
        with self.assertRaisesRegex(ValueError, 'fingerprint changed'):
            self.run_fake(requests, backend, resume=True)
        requests[0]['messages'][0]['content'] = '3'
        journal = self.root / 'run' / 'journal.jsonl'
        events = read_jsonl(journal)
        next(e for e in events if e['event'] == 'result')['prediction']['request_sha256'] = 'tampered'
        write_jsonl(journal, events)
        with self.assertRaisesRegex(ValueError, 'Journal prediction fingerprint mismatch'):
            self.run_fake(requests, backend, resume=True)

    def test_interrupted_request_is_not_reissued(self):
        requests = self.requests(3, 4)
        backend = FakeBackend(interrupt=True)
        with self.assertRaises(KeyboardInterrupt):
            self.run_fake(requests, backend)
        backend.interrupt = False
        result = self.run_fake(requests, backend, resume=True)
        self.assertEqual(result['counts'], {'interrupted_not_retried': 1, 'completed': 1})
        self.assertEqual(backend.calls, 2)
        self.assertEqual(read_jsonl(self.root / 'run' / 'predictions.jsonl')[0]['status'], 'interrupted_not_retried')

    def test_load_failure_preserves_all_planned_rows(self):
        backend = FakeBackend()
        def broken_load():
            raise RuntimeError('test out of memory')
        backend.load = broken_load
        result = self.run_fake(self.requests(3, 4), backend)
        self.assertEqual(result['counts'], {'backend_load_error': 2})
        self.assertEqual(backend.calls, 0)

    def test_no_overwrite_and_stale_lock_blocks_resume(self):
        self.run_fake(self.requests(3), FakeBackend())
        with self.assertRaises(FileExistsError):
            self.run_fake(self.requests(3), FakeBackend())
        (self.root / 'run' / '.running.lock').write_text('')
        with self.assertRaisesRegex(ValueError, 'locked'):
            self.run_fake(self.requests(3), FakeBackend(), resume=True)

    def test_request_gold_isolation_and_budget_checks(self):
        prepare(self.data, self.root / 'prepared', ['full', 'none', 'closure'], [64])
        requests = read_jsonl(self.root / 'prepared' / 'requests.jsonl')
        samples = read_jsonl(self.data)
        verify_requests(requests, samples, FakeBackend(), allow_fixture_units=True)
        with self.assertRaises(ValueError):
            verify_requests(requests, samples, FakeBackend())
        altered = copy.deepcopy(requests)
        altered[0]['messages'][1]['content'] += '\nGOLD: 129 CNY'
        with self.assertRaisesRegex(ValueError, 'Messages differ'):
            verify_requests(altered, samples, FakeBackend(), True)
        altered = copy.deepcopy(requests)
        altered[0]['budget_unit'] = 'target_tokenizer'
        with self.assertRaisesRegex(ValueError, 'count mismatch'):
            verify_requests(altered, samples, FakeBackend(), True)

    def test_prediction_request_binding_at_scoring(self):
        prepare(self.data, self.root / 'prepared', ['full'], [64])
        request_file = self.root / 'prepared' / 'requests.jsonl'
        requests = read_jsonl(request_file)
        predictions = [{'id': r['id'], 'request_sha256': digest(r), 'output': None} for r in requests]
        pred_file = self.root / 'predictions.jsonl'
        write_jsonl(pred_file, predictions)
        evaluate(self.data, request_file, pred_file, self.root / 'score')
        predictions[0]['request_sha256'] = 'different request'
        write_jsonl(pred_file, predictions)
        with self.assertRaisesRegex(ValueError, 'fingerprint mismatch'):
            evaluate(self.data, request_file, pred_file, self.root / 'score')


if __name__ == '__main__':
    unittest.main()
