"""Validate annotation structure and split isolation; never certify semantics."""
from __future__ import annotations
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit

ID = re.compile(r'^[A-Za-z0-9_-]+$')
FIXTURE = 'HAND_CONSTRUCTED_SOFTWARE_FIXTURE_NOT_WEB_DATA'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def strict_json(text):
    def bad_constant(value):
        raise ValueError(f'Non-finite JSON number: {value}')
    return json.loads(text, object_pairs_hook=unique_object,
                      parse_constant=bad_constant)


def read_rows(path):
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
        if line.strip():
            try:
                rows.append(strict_json(line))
            except ValueError as exc:
                raise ValueError(f'{path}:{number}: {exc}') from exc
    return rows


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate_dataset(rows, profile='basic', snapshot_root=None):
    require(profile in {'basic', 'web'}, 'Unknown validation profile')
    require(isinstance(rows, list) and bool(rows), 'Dataset must be nonempty')
    if profile == 'web':
        require(snapshot_root is not None, 'Web profile requires --snapshot-root')
    root = Path(snapshot_root).resolve() if snapshot_root is not None else None
    ids, split_keys, split_counts = set(), {}, {}
    split_present = [isinstance(r, dict) and 'split' in r for r in rows]
    require(not any(split_present) or all(split_present), 'Specify split for every sample or none')
    document_count = sentence_count = 0

    def isolate(key, split):
        if split is None:
            return
        require(key not in split_keys or split_keys[key] == split,
                f'Cross-split overlap: {key[0]} appears in {split_keys.get(key)} and {split}')
        split_keys[key] = split

    for index, row in enumerate(rows):
        label = f'row {index + 1}'
        require(isinstance(row, dict), f'{label}: expected object')
        for key in ('id', 'cluster_id', 'question', 'provenance'):
            require(nonempty(row.get(key)), f'{label}: missing/non-string {key}')
        require(row['id'] not in ids, f'Duplicate sample ID: {row["id"]}')
        ids.add(row['id'])
        split = row.get('split')
        if 'split' in row:
            require(split in {'train', 'dev', 'test'}, f'{label}: split must be train/dev/test')
            split_counts[split] = split_counts.get(split, 0) + 1
        isolate(('cluster', row['cluster_id']), split)
        isolate(('question', ' '.join(row['question'].casefold().split())), split)
        if profile == 'web':
            require(split is not None, f'{label}: web data requires split')
            require(row['provenance'] != FIXTURE, f'{label}: software fixture is not Web data')
        documents = row.get('documents')
        require(isinstance(documents, list) and bool(documents), f'{label}: documents must be nonempty')
        doc_ids, sentence_ids = set(), set()
        for doc in documents:
            require(isinstance(doc, dict), f'{label}: invalid document')
            doc_id = doc.get('doc_id')
            require(isinstance(doc_id, str) and ID.fullmatch(doc_id), f'{label}: invalid doc_id')
            require(doc_id not in doc_ids, f'{label}: duplicate doc_id {doc_id}')
            doc_ids.add(doc_id)
            for key in ('title', 'source', 'snapshot'):
                require(nonempty(doc.get(key)), f'{label}/{doc_id}: missing {key}')
            sentences = doc.get('sentences')
            require(isinstance(sentences, list) and bool(sentences), f'{label}/{doc_id}: empty sentences')
            for sentence in sentences:
                require(isinstance(sentence, dict), f'{label}: invalid sentence')
                sid = sentence.get('sid')
                require(isinstance(sid, str) and ID.fullmatch(sid), f'{label}: invalid sid')
                full_id = f'{doc_id}:{sid}'
                require(full_id not in sentence_ids, f'{label}: duplicate sentence {full_id}')
                sentence_ids.add(full_id)
                require(nonempty(sentence.get('paragraph')) and nonempty(sentence.get('text')),
                        f'{label}/{full_id}: paragraph and text must be nonempty strings')
            text_key = '\n'.join(' '.join(s['text'].casefold().split()) for s in sentences)
            isolate(('document text', hashlib.sha256(text_key.encode()).hexdigest()), split)
            document_count += 1
            sentence_count += len(sentences)
            if profile == 'web':
                url = urlsplit(doc['source'])
                require(url.scheme in {'https', 'http'} and bool(url.hostname)
                        and url.username is None and url.password is None,
                        f'{label}/{doc_id}: source must be an HTTP(S) URL without credentials')
                isolate(('source URL', urlunsplit((url.scheme.lower(), url.netloc.lower(), url.path, url.query, ''))), split)
                try:
                    timestamp = datetime.fromisoformat(doc['snapshot'].replace('Z', '+00:00'))
                except ValueError as exc:
                    raise ValueError(f'{label}/{doc_id}: snapshot must be an ISO capture timestamp') from exc
                require(timestamp.tzinfo is not None, f'{label}/{doc_id}: snapshot needs timezone')
                sha = doc.get('content_sha256')
                require(isinstance(sha, str) and re.fullmatch('[0-9a-f]{64}', sha), f'{label}: invalid content_sha256')
                relative = doc.get('snapshot_path')
                require(nonempty(relative) and not Path(relative).is_absolute(), f'{label}: snapshot_path must be relative')
                snapshot_file = (root / relative).resolve()
                require(snapshot_file.is_relative_to(root), f'{label}: snapshot_path escapes root')
                require(snapshot_file.is_file(), f'{label}: snapshot file missing')
                require(file_sha256(snapshot_file) == sha, f'{label}: snapshot hash mismatch')
                isolate(('snapshot hash', sha), split)
        gold = row.get('gold')
        require(isinstance(gold, dict) and type(gold.get('abstain')) is bool, f'{label}: gold.abstain must be boolean')
        answers, sets = gold.get('answers'), gold.get('evidence_sets')
        require(isinstance(answers, list) and all(nonempty(a) for a in answers), f'{label}: invalid gold.answers')
        aliases = [' '.join(a.casefold().split()) for a in answers]
        require(len(set(aliases)) == len(aliases), f'{label}: duplicate answer aliases')
        require(isinstance(sets, list), f'{label}: evidence_sets must be a list')
        seen_sets = set()
        for evidence in sets:
            require(isinstance(evidence, list) and bool(evidence) and all(isinstance(s, str) for s in evidence),
                    f'{label}: evidence set must be a nonempty ID list')
            require(len(set(evidence)) == len(evidence), f'{label}: repeated evidence ID')
            require(set(evidence) <= sentence_ids, f'{label}: unknown gold evidence ID')
            key = frozenset(evidence)
            require(key not in seen_sets, f'{label}: duplicate evidence set')
            seen_sets.add(key)
        require((not answers and not sets) if gold['abstain'] else (bool(answers) and bool(sets)),
                f'{label}: answerability contradicts gold answers/evidence')
    return {'status': 'STRUCTURE_VALID_NOT_SEMANTICALLY_CERTIFIED', 'profile': profile,
            'samples': len(rows), 'clusters': len({r['cluster_id'] for r in rows}),
            'documents': document_count, 'sentences': sentence_count, 'splits': split_counts,
            'limitations': ['No semantic support, license, extraction fidelity or near-duplicate certification.',
                           'No split isolation check when split is omitted.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True)
    parser.add_argument('--profile', choices=['basic', 'web'], default='basic')
    parser.add_argument('--snapshot-root')
    args = parser.parse_args()
    result = validate_dataset(read_rows(args.data), args.profile, args.snapshot_root)
    result['data_file_sha256'] = file_sha256(args.data)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
