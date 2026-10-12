"""Tests verify research invariants, not model quality."""
import copy
import json
from pathlib import Path
from contextlib import contextmanager
import uuid
import unittest
from prototype import (closure, public_input, read_jsonl, CounterUnits, select,
                       render, nodes_of, score_one, prepare, evaluate, write_jsonl)

class ResearchInvariants(unittest.TestCase):
    def setUp(self):
        self.path = Path(__file__).with_name('demo.jsonl')
        self.samples = read_jsonl(self.path)
        self.scratch = Path(__file__).resolve().parents[1] / 'work' / 'unit-tests'
        self.scratch.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def workspace_directory(self):
        # tempfile's private directory permissions are incompatible with this
        # Windows sandbox. Ordinary workspace folders inherit usable ACLs.
        d = self.scratch / uuid.uuid4().hex
        d.mkdir()
        yield d

    def test_cycles_and_transitive_dependencies(self):
        self.assertEqual(closure({'a'}, {('a','b'),('b','a'),('b','c')}), {'a','b','c'})

    def test_exact_rendered_budget_and_closure(self):
        count = CounterUnits()
        for sample in self.samples:
            pub = public_input(sample)
            nodes = nodes_of(pub)
            for method in ['head','bm25','neighbors','closure']:
                for budget in [0,1,32,64,128,256]:
                    chosen, edges = select(pub, method, budget, count)
                    self.assertLessEqual(count(render(nodes, chosen)), budget)
                    self.assertEqual(closure(chosen, edges), chosen)

    def test_no_gold_leakage(self):
        s = self.samples[0]
        other = copy.deepcopy(s)
        other['gold'] = {'answers':['MALICIOUS GOLD'], 'evidence_sets':[['D2:s1']]}
        other['task_type'] = 'different'
        self.assertEqual(public_input(s), public_input(other))
        self.assertEqual(select(public_input(s),'closure',128,CounterUnits()),
                         select(public_input(other),'closure',128,CounterUnits()))

    def test_wrong_and_invisible_citations(self):
        gold = {'answers':['129 CNY'],'evidence_sets':[['D1:s1','D1:s2']]}
        p = {'answer':'129 CNY','citations':['D2:s1'],'abstain':False}
        scores = score_one(gold,p,{'D1:s1','D1:s2','D2:s1'})
        self.assertEqual(scores['answer_em'],1)
        self.assertEqual(scores['joint_exact_evidence'],0)
        self.assertEqual(score_one(gold,p,{'D1:s1'})['valid'],0)

    def test_refusal_and_malformed_prediction(self):
        g = {'abstain':True}
        self.assertEqual(score_one(g,{'answer':'','citations':[],'abstain':True},set())['answer_em'],1)
        self.assertEqual(score_one(g,{'answer':'','citations':[],'abstain':'true'},set())['valid'],0)
        self.assertEqual(score_one(g,None,set())['answer_em'],0)

    def test_missing_predictions_remain_in_denominator(self):
        with self.workspace_directory() as d:
            prepare(self.path,d,['full'],[64])
            p=Path(d)/'empty.jsonl'
            write_jsonl(p,[])
            summary=evaluate(self.path,Path(d)/'requests.jsonl',p,d)
            self.assertEqual(summary[0]['n'],len(self.samples))
            self.assertEqual(summary[0]['missing'],100)
            self.assertEqual(summary[0]['answer_em'],0)

    def test_duplicate_predictions_rejected(self):
        with self.workspace_directory() as d:
            prepare(self.path,d,['full'],[64])
            rid=read_jsonl(Path(d)/'requests.jsonl')[0]['id']
            p=Path(d)/'dup.jsonl'
            write_jsonl(p,[{'id':rid},{'id':rid}])
            with self.assertRaises(ValueError):
                evaluate(self.path,Path(d)/'requests.jsonl',p,d)

if __name__ == '__main__':
    unittest.main(verbosity=2)
