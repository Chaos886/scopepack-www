"""Annotation validation tests use fictional fixtures only."""
import copy
from pathlib import Path
import unittest
import uuid

from validate_data import file_sha256, read_rows, strict_json, validate_dataset


class DataValidationTests(unittest.TestCase):
    def setUp(self):
        self.samples = read_rows(Path(__file__).with_name('demo.jsonl'))

    def test_demo_structure_and_not_web(self):
        result = validate_dataset(self.samples)
        self.assertEqual(result['samples'], 8)
        with self.assertRaises(ValueError):
            validate_dataset(self.samples, 'web', '.')

    def test_invalid_ids_gold_and_answerability(self):
        mutations = [lambda s: s['documents'].append(copy.deepcopy(s['documents'][0])),
                     lambda s: s['gold']['evidence_sets'].append(['D9:missing']),
                     lambda s: s['gold'].update(abstain=True),
                     lambda s: s['documents'][0]['sentences'][0].update(text=''),
                     lambda s: s['gold']['answers'].append(s['gold']['answers'][0].upper())]
        for mutate in mutations:
            sample = copy.deepcopy(self.samples[0])
            mutate(sample)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                validate_dataset([sample])

    def test_split_cluster_question_and_document_leakage(self):
        a, b = copy.deepcopy(self.samples[:2])
        a['split'], b['split'] = 'train', 'test'
        validate_dataset([a, b])
        for field in ('cluster_id', 'question', 'documents'):
            leaked = copy.deepcopy(b)
            leaked[field] = copy.deepcopy(a[field])
            if field == 'documents':
                leaked['gold'] = copy.deepcopy(a['gold'])
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'Cross-split'):
                validate_dataset([a, leaked])
        del b['split']
        with self.assertRaisesRegex(ValueError, 'every sample'):
            validate_dataset([a, b])
        b['split'] = None
        with self.assertRaisesRegex(ValueError, 'split must'):
            validate_dataset([a, b])

    def test_snapshot_bytes_timestamp_and_path_escape(self):
        root = Path(__file__).resolve().parents[1] / 'work' / 'unit-tests' / uuid.uuid4().hex
        root.mkdir(parents=True)
        sample = copy.deepcopy(self.samples[0])
        sample.update(provenance='TEST_ONLY_ARTIFICIAL_METADATA', split='dev')
        for i, doc in enumerate(sample['documents']):
            asset = root / f'{i}.html'
            asset.write_text(f'<p>TEST ONLY {i}</p>', encoding='utf-8')
            doc.update(source=f'https://example.org/{i}', snapshot='2026-10-10T12:00:00+08:00',
                       snapshot_path=asset.name, content_sha256=file_sha256(asset))
        validate_dataset([sample], 'web', root)
        for update in ({'content_sha256': '0' * 64}, {'snapshot': '2026-10-10'},
                       {'snapshot_path': '../escape.html'}, {'source': 'synthetic://fake'},
                       {'source': 'https://:password@example.org/policy'}):
            broken = copy.deepcopy(sample)
            broken['documents'][0].update(update)
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate_dataset([broken], 'web', root)

    def test_duplicate_and_nonfinite_json_rejected(self):
        for text in ('{"id":1,"id":2}', '{"a":NaN}', '{"a":Infinity}'):
            with self.assertRaises(ValueError):
                strict_json(text)


if __name__ == '__main__':
    unittest.main()
