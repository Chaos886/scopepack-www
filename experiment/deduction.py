"""Controlled deduction diagnostics, not a natural Web benchmark or LLM result.

Semantics: finite, ground signed atoms; conjunctive forward rules; open world;
explicit negation; no contraposition, converse, default negation or explosion.
The symbolic program is evaluation-only and never enters public_input().
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from itertools import product
import json
from pathlib import Path
import random
import re

from validate_data import FIXTURE, file_sha256, read_rows, require, validate_dataset

VERSION = 'scopepack-ground-deduction-v1'
LABELS = ('entailed', 'contradicted', 'unknown')
ATOM = re.compile(r'^[a-z][a-z0-9_]{0,40}$')
SEMANTICS = (
    'Use only the stated facts and forward rules for this fictional case. '
    'A rule fires only when every stated premise has been established. '
    'Do not reverse rules or use contraposition. Missing information is not negation. '
    'If the query follows, answer "entailed"; if its explicit negation follows, '
    'answer "contradicted". In either case set abstain=false and cite a sufficient '
    'set of fact and rule sentence IDs. If neither follows, set abstain=true, '
    'answer="", and citations=[]. No other knowledge is permitted. '
    'Question: Is the following statement supported? '
)


def opposite(literal):
    return literal[1:] if literal.startswith('!') else '!' + literal


def solve(clauses, selected=None, max_proofs=256):
    """Return all subset-minimal supports and minimal rule depth per literal.

    Depth counts the longest rule chain, not proof size: facts have depth 0.
    Caps fail explicitly rather than silently discarding alternative proofs.
    Inputs are validated by validate_program before dataset use.
    """
    active = [c for c in clauses if selected is None or c['id'] in selected]
    proofs, depths = defaultdict(set), {}

    def insert(literal, support):
        current = proofs[literal]
        if any(old <= support for old in current):
            return False
        current.difference_update(old for old in list(current) if support < old)
        current.add(support)
        require(len(current) <= max_proofs, 'Proof enumeration cap exceeded; simplify or use a different solver')
        return True

    for clause in active:
        if clause['kind'] == 'fact':
            insert(clause['literal'], frozenset([clause['id']]))
            depths[clause['literal']] = 0
    changed, work = True, 0
    while changed:
        changed = False
        for clause in active:
            if clause['kind'] != 'rule' or not all(proofs[p] for p in clause['premises']):
                continue
            target = clause['conclusion']
            candidate_depth = 1 + max(depths[p] for p in clause['premises'])
            if target not in depths or candidate_depth < depths[target]:
                depths[target] = candidate_depth
                changed = True
            alternatives = [sorted(proofs[p], key=lambda x: (len(x), sorted(x))) for p in clause['premises']]
            for support_tuple in product(*alternatives):
                work += 1
                require(work <= 100000, 'Proof search cap exceeded; no partial result is accepted')
                support = frozenset([clause['id']]).union(*support_tuple)
                changed = insert(target, support) or changed
    return dict(proofs), depths


def classify(proofs, query):
    positive, negative = bool(proofs.get(query)), bool(proofs.get(opposite(query)))
    if positive and negative:
        return 'inconsistent'
    return 'entailed' if positive else 'contradicted' if negative else 'unknown'


def literal_text(entity, literal):
    negative = literal.startswith('!')
    return f'case {entity} ' + ('does not have' if negative else 'has') + f' attribute {literal.lstrip("!")}'


def clause_text(entity, clause):
    if clause['kind'] == 'fact':
        return literal_text(entity, clause['literal']).capitalize() + '.'
    return ('If ' + ' and '.join(literal_text(entity, p) for p in clause['premises'])
            + ', then ' + literal_text(entity, clause['conclusion']) + '.')


def question_text(entity, query):
    return SEMANTICS + literal_text(entity, query) + '?'


def validate_program(sample):
    """Verify exact controlled-English rendering and gold against the formal program."""
    program = sample.get('deduction')
    require(isinstance(program, dict) and program.get('version') == VERSION, 'Invalid deduction version')
    require(sample.get('provenance') == FIXTURE, 'Controlled deduction must be marked as a software fixture')
    require(program.get('label') in LABELS, 'Unknown deduction label')
    entity, query = program.get('entity'), program.get('query')
    require(isinstance(entity, str) and ATOM.fullmatch(entity), 'Invalid entity')

    def check_literal(literal):
        require(isinstance(literal, str) and ATOM.fullmatch(literal[1:] if literal.startswith('!') else literal),
                'Invalid signed ground atom')
    check_literal(query)
    clauses = program.get('clauses')
    require(isinstance(clauses, list) and 0 < len(clauses) <= 64, 'Expected 1..64 clauses')
    sentences = {f'{d["doc_id"]}:{s["sid"]}': s['text'] for d in sample['documents'] for s in d['sentences']}
    seen = set()
    for clause in clauses:
        require(isinstance(clause, dict) and isinstance(clause.get('id'), str), 'Invalid clause')
        cid = clause['id']
        require(cid not in seen and cid in sentences, 'Missing/duplicate clause sentence ID')
        seen.add(cid)
        if clause.get('kind') == 'fact':
            require(set(clause) == {'id', 'kind', 'literal'}, 'Unexpected fact fields')
            check_literal(clause['literal'])
        else:
            require(clause.get('kind') == 'rule' and set(clause) == {'id', 'kind', 'premises', 'conclusion'}, 'Invalid rule fields')
            premises = clause['premises']
            require(isinstance(premises, list) and 1 <= len(premises) <= 4, 'Rules require 1..4 premises')
            for premise in premises:
                check_literal(premise)
            require(len(set(premises)) == len(premises), 'Duplicate premise')
            check_literal(clause['conclusion'])
        require(sentences[cid] == clause_text(entity, clause), 'Sentence text differs from its formal clause')
    require(seen == set(sentences), 'Every sentence must map to exactly one clause')
    require(sample['question'] == question_text(entity, query), 'Question differs from formal query/semantics')
    proofs, depths = solve(clauses)
    require(not any(supports and proofs.get(opposite(atom)) for atom, supports in proofs.items()),
            'Inconsistent theory is outside this diagnostic track')
    label = classify(proofs, query)
    require(label == program['label'], 'Gold label disagrees with symbolic derivation')
    conclusion = query if label == 'entailed' else opposite(query)
    depth = depths.get(conclusion) if label != 'unknown' else None
    require(program.get('proof_depth') == depth and (depth is None or type(program['proof_depth']) is int),
            'Incorrect shortest proof depth')
    require(type(program.get('template_depth')) is int and 0 <= program['template_depth'] <= 8, 'Invalid template depth')
    require(isinstance(program.get('pair_id'), str) and program['pair_id'], 'Missing paired-world identifier')
    gold = sample['gold']
    if label == 'unknown':
        require(gold == {'answers': [], 'evidence_sets': [], 'abstain': True}, 'Unknown needs strict abstention gold')
    else:
        require(gold['answers'] == [label] and gold['abstain'] is False, 'Invalid deduction answer gold')
        require({frozenset(s) for s in gold['evidence_sets']} == proofs[conclusion],
                'Gold evidence must include all subset-minimal proofs')
    return {'label': label, 'proof_depth': depth, 'minimal_proofs': len(proofs.get(conclusion, [])) if label != 'unknown' else 0}


def predicted_label(output, valid):
    if not valid:
        return 'invalid'
    if output['abstain']:
        return 'unknown' if not output['answer'].strip() and not output['citations'] else 'invalid'
    answer = ' '.join(output['answer'].casefold().split())
    return answer if answer in LABELS[:2] else 'invalid'


def score_deduction(sample, output, selected, base_scores):
    """Formal diagnostics use only saved annotations, never model-generated prose."""
    program = sample['deduction']
    clauses, query, label = program['clauses'], program['query'], program['label']
    visible, _ = solve(clauses, set(selected))
    visible_label = classify(visible, query)
    predicted = predicted_label(output, base_scores['valid'])
    supported = None
    if label != 'unknown':
        cited, _ = solve(clauses, set(output['citations'])) if base_scores['valid'] else ({}, {})
        supported = int(predicted == label and classify(cited, query) == label)
    return {'deduction_label': label, 'deduction_prediction': predicted,
            'deduction_pair_id': program['pair_id'], 'proof_depth': program['proof_depth'],
            'template_depth': program['template_depth'], 'visible_label': visible_label,
            'logic_label_correct': int(predicted == label),
            'visible_label_correct': int(predicted == visible_label),
            'proof_retained': int(visible_label == label) if label != 'unknown' else None,
            'proof_supported_correct': supported}


def make_suite(seed=2026, families=4, depths=(0, 1, 2, 3, 4), split='dev'):
    """Balanced matched worlds; seed changes vocabulary/order, not template diversity."""
    require(type(seed) is int and seed >= 0, 'Seed must be nonnegative')
    require(type(families) is int and 1 <= families <= 100, 'Use 1..100 families')
    require(split in {'train', 'dev', 'test'}, 'Invalid split')
    require(bool(depths) and len(set(depths)) == len(depths)
            and all(type(d) is int and 0 <= d <= 8 for d in depths), 'Unique depths must be in 0..8')
    samples = []
    for family in range(families):
        cluster = f'deduction_{seed}_family_{family}'
        for depth in depths:
            # Label variants reuse vocabulary and shuffling, so IDs/positions do not encode labels.
            rng = random.Random(f'{seed}/{family}/{depth}')
            names = ['p' + ''.join(rng.choices('abcdefghijklmnopqrstuvwxyz', k=10)) for _ in range(2 * depth + 9)]
            require(len(names) == len(set(names)), 'Atom collision; choose another seed')
            path = names[:depth + 1]
            gates = [('!' if (family + i) % 2 else '') + atom
                     for i, atom in enumerate(names[depth + 1:2 * depth + 1])]
            spare, lure, loop_a, loop_b, unrelated = names[-5:]
            entity = 'e' + ''.join(rng.choices('abcdefghijklmnopqrstuvwxyz', k=10))
            pair = f'{cluster}_depth_{depth}'
            for label_index, label in enumerate(LABELS):
                clauses = []
                def fact(literal):
                    clauses.append({'kind': 'fact', 'literal': literal})
                def rule(premises, conclusion):
                    clauses.append({'kind': 'rule', 'premises': premises, 'conclusion': conclusion})
                target = path[-1]
                fact(spare if label == 'unknown' else ('!' + target if depth == 0 and label == 'contradicted' else path[0]))
                for step in range(depth):
                    fact(gates[step])
                    conclusion = path[step + 1]
                    if step == depth - 1 and label == 'contradicted':
                        conclusion = '!' + conclusion
                    rule([path[step], gates[step]], conclusion)
                # Tempting converse and an unsupported cycle are present in every world.
                rule([target], lure)
                fact(lure)
                rule([loop_a], loop_b)
                rule([loop_b], loop_a)
                # Both polarities of the target occur in each world; surface mention
                # alone cannot distinguish derivability from an unsupported rule.
                rule([loop_a], target if label == 'contradicted' else '!' + target)
                fact('!' + unrelated)
                local_rng = random.Random(f'order/{seed}/{family}/{depth}')
                local_rng.shuffle(clauses)
                docs = [{'doc_id': f'D{d + 1}', 'title': f'Constructed registry {d + 1}',
                         'source': f'synthetic://deduction/{cluster}/D{d + 1}', 'snapshot': VERSION,
                         'sentences': []} for d in range(3)]
                for number, clause in enumerate(clauses):
                    doc = docs[number % len(docs)]
                    sid = f's{len(doc["sentences"]) + 1}'
                    clause['id'] = f'{doc["doc_id"]}:{sid}'
                    doc['sentences'].append({'sid': sid, 'paragraph': f'p{number + 1}',
                                             'text': clause_text(entity, clause)})
                proofs, proof_depths = solve(clauses)
                require(classify(proofs, target) == label, 'Generator/oracle mismatch')
                conclusion = target if label == 'entailed' else '!' + target
                evidence = sorted([sorted(s) for s in proofs.get(conclusion, [])]) if label != 'unknown' else []
                samples.append({'id': f'{pair}_world_{label_index}', 'cluster_id': cluster,
                    'split': split, 'task_type': 'controlled_deduction', 'provenance': FIXTURE,
                    'question': question_text(entity, target), 'documents': docs,
                    'gold': {'answers': [label] if label != 'unknown' else [],
                             'evidence_sets': evidence, 'abstain': label == 'unknown'},
                    'deduction': {'version': VERSION, 'entity': entity, 'query': target,
                                  'clauses': clauses, 'label': label, 'pair_id': pair,
                                  'template_depth': depth,
                                  'proof_depth': proof_depths.get(conclusion) if label != 'unknown' else None}})
    return samples


def inventory(samples):
    validate_dataset(samples)
    require(all('deduction' in s for s in samples), 'All rows must belong to the deduction track')
    return {'status': 'SYMBOLIC_FIXTURE_VALIDATED_NO_LLM_INFERENCE', 'version': VERSION,
            'samples': len(samples), 'clusters': len({s['cluster_id'] for s in samples}),
            'labels': dict(Counter(s['deduction']['label'] for s in samples)),
            'template_depths': dict(Counter(s['deduction']['template_depth'] for s in samples)),
            'limits': ['Controlled templates, not natural Web data or broad intelligence measurement.',
                       'Renaming atoms does not create independent reasoning templates.',
                       'Unknown has no finite proof depth; template_depth is only a construction setting.']}


def pct(n, d):
    return 100 * n / d if d else None


def summarize(rows):
    """Each rate includes its denominator. No silent pairing or failure filtering."""
    answerable = [r for r in rows if r['deduction_label'] != 'unknown']
    retained = [r for r in answerable if r['proof_retained']]
    by_label = {label: [r for r in rows if r['deduction_label'] == label] for label in LABELS}
    recalls = {label: pct(sum(r['logic_label_correct'] for r in group), len(group)) for label, group in by_label.items()}
    confusion = {label: dict(Counter(r['deduction_prediction'] for r in group)) for label, group in by_label.items()}
    return {'n': len(rows), 'answer_accuracy_pct': pct(sum(r['logic_label_correct'] for r in rows), len(rows)),
            'label_counts': {k: len(v) for k, v in by_label.items()}, 'per_label_accuracy_pct': recalls,
            'macro_three_label_accuracy_pct': sum(recalls.values()) / 3 if all(v is not None for v in recalls.values()) else None,
            'confusion': confusion, 'answerable_n': len(answerable),
            'proof_retained_n': len(retained), 'proof_retention_pct': pct(len(retained), len(answerable)),
            'answer_accuracy_given_proof_retained_pct': pct(sum(r['logic_label_correct'] for r in retained), len(retained)),
            'proof_supported_correct_pct': pct(sum(r['proof_supported_correct'] for r in answerable), len(answerable)),
            'visible_context_accuracy_pct': pct(sum(r['visible_label_correct'] for r in rows), len(rows)),
            'missing_n': sum(r['missing'] for r in rows),
            'invalid_prediction_n': sum(r['deduction_prediction'] == 'invalid' for r in rows),
            'proof_lost_and_answer_wrong_n': sum(not r['proof_retained'] and not r['logic_label_correct'] for r in answerable),
            'proof_retained_but_answer_wrong_n': sum(not r['logic_label_correct'] for r in retained)}


def build_report(rows):
    from analyze import load_groups
    load_groups(rows)  # Existing validity, missing-denominator and duplicate checks.
    groups = defaultdict(list)
    for row in rows:
        require(row.get('deduction_label') in LABELS and row.get('deduction_prediction') in (*LABELS, 'invalid'),
                'Expected deduction scores only; regenerate with current evaluate')
        require(row.get('visible_label') in LABELS, 'Invalid visible label')
        require(isinstance(row.get('deduction_pair_id'), str) and row['deduction_pair_id'], 'Missing deduction pair ID')
        require(type(row.get('template_depth')) is int and 0 <= row['template_depth'] <= 8, 'Invalid template depth')
        unknown = row['deduction_label'] == 'unknown'
        for key in ('logic_label_correct', 'visible_label_correct'):
            require(type(row.get(key)) is int and row[key] in (0, 1), f'Invalid {key}')
        require(row['logic_label_correct'] == int(row['deduction_prediction'] == row['deduction_label'])
                and row['visible_label_correct'] == int(row['deduction_prediction'] == row['visible_label']),
                'Contradictory deduction accuracy fields')
        require(row['logic_label_correct'] == row['answer_em'], 'Logical and generic answer scores disagree')
        if unknown:
            require(row.get('proof_depth') is None and row.get('proof_retained') is None
                    and row.get('proof_supported_correct') is None, 'Unknown cases have no positive proof score')
        else:
            require(type(row.get('proof_depth')) is int and row['proof_depth'] >= 0, 'Missing proof depth')
            for key in ('proof_retained', 'proof_supported_correct'):
                require(type(row.get(key)) is int and row[key] in (0, 1), f'Invalid {key}')
            require(row['proof_retained'] == int(row['visible_label'] == row['deduction_label']), 'Wrong retention flag')
            require(row['proof_supported_correct'] <= min(row['logic_label_correct'], row['proof_retained']),
                    'Unsupported proof success')
        groups[(row['method'], row['budget'])].append(row)
    summaries = []
    for (method, budget), group in sorted(groups.items()):
        pairs, depth_groups = defaultdict(list), defaultdict(list)
        for row in group:
            pairs[row['deduction_pair_id']].append(row)
            depth_groups[row['template_depth']].append(row)
        complete, incomplete = [], 0
        for members in pairs.values():
            require(len({r['deduction_label'] for r in members}) == len(members), 'Duplicate label in paired worlds')
            require(len({(r['cluster_id'], r['template_depth']) for r in members}) == 1, 'Pair cluster/depth mismatch')
            if len(members) == 3:
                complete.append(int(all(r['logic_label_correct'] for r in members)))
            else:
                incomplete += 1
        summaries.append({'method': method, 'budget': budget, **summarize(group),
                          'complete_world_triplets': len(complete), 'incomplete_world_triplets': incomplete,
                          'all_three_worlds_correct_pct': pct(sum(complete), len(complete)),
                          'by_template_depth': {str(d): summarize(rs) for d, rs in sorted(depth_groups.items())}})
    return {'status': 'ANALYSIS_OF_SUPPLIED_PREDICTIONS_NOT_AUTHENTICATED_MODEL_RESULTS',
            'groups': summaries, 'warnings': [
                'Conditional accuracy uses method-dependent subsets and is not a causal method comparison.',
                'Proof-retained failures also include parsing, protocol and infrastructure failures.',
                'Citations form a checkable support certificate, not a record of internal reasoning.',
                'Use paired cluster analysis for primary comparisons; template renamings are not independent templates.',
                'No real model inference or natural Web validity is certified by this report.']}


def report_markdown(report):
    lines = ['# Controlled deduction diagnostic', '', report['status'], '',
             '| Method | Budget | n | Label accuracy % | Proof retention % | Accuracy given proof % | Supported correct % |',
             '|---|---:|---:|---:|---:|---:|---:|']
    def show(value):
        return 'undefined' if value is None else f'{value:.2f}'
    for row in report['groups']:
        values = [show(row[k]) for k in ('answer_accuracy_pct', 'proof_retention_pct',
                  'answer_accuracy_given_proof_retained_pct', 'proof_supported_correct_pct')]
        lines.append(f'| {row["method"]} | {row["budget"]} | {row["n"]} | ' + ' | '.join(values) + ' |')
    lines += ['', 'Denominators, label confusion, template depths and matched worlds are in the JSON report.', '']
    lines.extend('- ' + warning for warning in report['warnings'])
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    gen = sub.add_parser('generate')
    gen.add_argument('--out', required=True)
    gen.add_argument('--seed', type=int, default=2026)
    gen.add_argument('--families', type=int, default=4)
    gen.add_argument('--depths', nargs='+', type=int, default=[0, 1, 2, 3, 4])
    gen.add_argument('--split', choices=['train', 'dev', 'test'], default='dev')
    inspect = sub.add_parser('inspect')
    inspect.add_argument('--data', required=True)
    report = sub.add_parser('report')
    report.add_argument('--scores', required=True)
    report.add_argument('--out', required=True)
    args = parser.parse_args()
    if args.command == 'generate':
        samples = make_suite(args.seed, args.families, tuple(args.depths), args.split)
        result = inventory(samples)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=False)
        with (out / 'data.jsonl').open('w', encoding='utf-8', newline='\n') as stream:
            for sample in samples:
                stream.write(json.dumps(sample, ensure_ascii=False) + '\n')
        result.update(seed=args.seed, families=args.families, depths=args.depths, split=args.split,
                      data_sha256=file_sha256(out / 'data.jsonl'), generator_sha256=file_sha256(__file__))
        (out / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    elif args.command == 'inspect':
        result = inventory(read_rows(args.data))
        result['data_sha256'] = file_sha256(args.data)
    else:
        result = build_report(read_rows(args.scores))
        result.update(scores_sha256=file_sha256(args.scores), code_sha256=file_sha256(__file__))
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=False)
        (out / 'deduction_report.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        (out / 'deduction_report.md').write_text(report_markdown(result), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
