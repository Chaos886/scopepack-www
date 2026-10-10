"""Local-only, serial Hugging Face inference with an auditable request journal.

No model downloads, paid calls, output repair, truncation or automatic retries.
The journal core is standard-library-only; the HF adapter needs torch/transformers.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import time
import uuid

from prototype import digest, nodes_of, public_input, render, SYSTEM, write_jsonl
from validate_data import (FIXTURE, file_sha256, nonempty, read_rows, require,
                           strict_json, validate_dataset)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def parse_output(raw):
    """Accept one complete JSON object only; never extract/repair an answer."""
    try:
        value = strict_json(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(value, dict) or set(value) != {'answer', 'citations', 'abstain'}:
        return None
    if not isinstance(value['answer'], str) or type(value['abstain']) is not bool:
        return None
    citations = value['citations']
    if not isinstance(citations, list) or not all(isinstance(x, str) for x in citations):
        return None
    return value


def load_config(path):
    config = strict_json(Path(path).read_text(encoding='utf-8-sig'))
    fields = {'schema_version', 'backend', 'model_path', 'tokenizer_path', 'model_revision',
              'device', 'dtype', 'max_context_tokens', 'max_new_tokens', 'seed'}
    require(isinstance(config, dict) and set(config) == fields, f'Config must contain exactly: {sorted(fields)}')
    require(type(config['schema_version']) is int and config['schema_version'] == 1
            and config['backend'] == 'huggingface_local', 'Unsupported config version/backend')
    require(nonempty(config['model_revision']), 'Record the exact upstream model revision')
    for key in ('model_path', 'tokenizer_path'):
        require(nonempty(config[key]), f'Set {key} to an existing local directory')
        target = Path(config[key])
        target = target if target.is_absolute() else Path(path).resolve().parent / target
        require(target.is_dir(), f'{key} directory does not exist; automatic downloads are disabled')
        config[key] = str(target.resolve())
    require(isinstance(config['device'], str) and re.fullmatch(r'cpu|cuda(?::\d+)?', config['device']), 'device must be cpu or cuda[:index]')
    require(config['dtype'] in {'float32', 'float16', 'bfloat16'}, 'Unsupported dtype')
    require(config['device'] != 'cpu' or config['dtype'] == 'float32', 'Use float32 for the CPU adapter')
    for key in ('max_context_tokens', 'max_new_tokens', 'seed'):
        require(type(config[key]) is int and config[key] >= (0 if key == 'seed' else 1), f'Invalid {key}')
    require(config['max_new_tokens'] < config['max_context_tokens'], 'Output allowance must leave input space')
    return config


def artifact_fingerprint(directory):
    """Hash local model/tokenizer assets, including all safetensors weight bytes."""
    root = Path(directory)
    suffixes = {'.json', '.safetensors', '.model', '.txt', '.jinja', '.tiktoken', '.bpe', '.vocab'}
    files = [p for p in root.rglob('*') if p.is_file() and p.suffix in suffixes
             and not any(part.startswith('.') for part in p.relative_to(root).parts)]
    require(bool(files), 'No local model/tokenizer assets found')
    return {p.relative_to(root).as_posix(): file_sha256(p) for p in sorted(files)}


class HFBackend:
    def __init__(self, config):
        try:
            import transformers
            from transformers import AutoConfig, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError('Local inference requires transformers and torch; see LOCAL_INFERENCE.md') from exc
        self.config = config
        self.model = None
        self.tokenizer = AutoTokenizer.from_pretrained(config['tokenizer_path'],
            local_files_only=True, trust_remote_code=False)
        require(bool(self.tokenizer.chat_template), 'Tokenizer must provide a chat template; no fallback is guessed')
        self.model_config = AutoConfig.from_pretrained(config['model_path'],
            local_files_only=True, trust_remote_code=False)
        require(not getattr(self.model_config, 'is_encoder_decoder', False), 'Only decoder-only causal language models are supported')
        for limit in (getattr(self.model_config, 'max_position_embeddings', None),
                      getattr(self.tokenizer, 'model_max_length', None)):
            if isinstance(limit, int) and 0 < limit < 10**9:
                require(config['max_context_tokens'] <= limit,
                        f'Configured context exceeds local model/tokenizer limit {limit}')
        model_assets = artifact_fingerprint(config['model_path'])
        require(any(name.endswith('.safetensors') for name in model_assets), 'Local safetensors weights are required')
        tokenizer_assets = (model_assets if config['model_path'] == config['tokenizer_path']
                            else artifact_fingerprint(config['tokenizer_path']))
        self.metadata = {'adapter': 'HF_LOCAL_ACTUAL_INFERENCE', 'transformers': transformers.__version__,
                         'torch': importlib.metadata.version('torch'), 'python': platform.python_version(),
                         'platform': platform.platform(), 'model_assets': model_assets,
                         'tokenizer_assets': tokenizer_assets,
                         'chat_template_sha256': digest(self.tokenizer.chat_template)}

    def count_text(self, text):
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def encode(self, messages):
        # Tokenize directly: adding special tokens a second time would corrupt the prompt.
        return self.tokenizer.apply_chat_template(messages, tokenize=True,
                    add_generation_prompt=True, truncation=False)

    def load(self):
        import torch
        from transformers import AutoModelForCausalLM, GenerationConfig, set_seed
        config = self.config
        require(not config['device'].startswith('cuda') or torch.cuda.is_available(), 'CUDA is unavailable')
        set_seed(config['seed'])
        self.model = AutoModelForCausalLM.from_pretrained(config['model_path'],
            local_files_only=True, trust_remote_code=False, use_safetensors=True,
            torch_dtype=getattr(torch, config['dtype']))
        self.model.to(config['device'])
        self.model.eval()
        # Carry over only special-token IDs. Do not inherit sampling, beam, forced-token,
        # minimum-length or repetition settings hidden in a checkpoint generation config.
        inherited = self.model.generation_config
        eos = inherited.eos_token_id if inherited.eos_token_id is not None else self.tokenizer.eos_token_id
        require(eos is not None, 'EOS token must be defined')
        self.eos_ids = eos if isinstance(eos, list) else [eos]
        pad = self.tokenizer.pad_token_id
        self.generation = GenerationConfig(max_new_tokens=config['max_new_tokens'],
            do_sample=False, num_beams=1, num_return_sequences=1, use_cache=True,
            eos_token_id=eos, pad_token_id=pad if pad is not None else self.eos_ids[0],
            bos_token_id=self.tokenizer.bos_token_id)
        self.runtime = {'device': config['device'], 'dtype': config['dtype'],
                        'cuda_version': torch.version.cuda,
                        'generation_config': self.generation.to_dict(),
                        'gpu': torch.cuda.get_device_name(torch.device(config['device']))
                               if config['device'].startswith('cuda') else None}

    def generate(self, tokens):
        import torch
        inputs = torch.tensor([tokens], dtype=torch.long, device=self.config['device'])
        if self.config['device'].startswith('cuda'):
            torch.cuda.synchronize(self.config['device'])
        start = time.perf_counter()
        with torch.inference_mode():
            output = self.model.generate(input_ids=inputs, attention_mask=torch.ones_like(inputs),
                                          generation_config=self.generation)
        generated = output[0, len(tokens):].tolist()
        if self.config['device'].startswith('cuda'):
            torch.cuda.synchronize(self.config['device'])
        duration = 1000 * (time.perf_counter() - start)
        return {'raw_text': self.tokenizer.decode(generated, skip_special_tokens=True),
                'generated_token_ids': generated, 'output_tokens': len(generated),
                'finish_reason': 'eos' if generated and generated[-1] in self.eos_ids else 'length_or_other',
                'generation_ms': duration}


def verify_requests(requests, samples, backend, allow_fixture_units=False):
    require(bool(requests), 'No requests')
    samples = {s['id']: s for s in samples}
    ids = set()
    for request in requests:
        require(isinstance(request, dict) and nonempty(request.get('id')), 'Invalid request row')
        require(request['id'] not in ids, 'Duplicate request ID')
        ids.add(request['id'])
        require(request.get('sample_id') in samples, 'Unknown sample ID')
        sample = samples[request['sample_id']]
        public = public_input(sample)
        require(request.get('input_hash') == digest(public), 'Request/data input hash mismatch')
        nodes = nodes_of(public)
        chosen = request.get('selected_ids')
        require(isinstance(chosen, list) and all(isinstance(x, str) for x in chosen), 'Invalid selected IDs')
        require(len(set(chosen)) == len(chosen) and set(chosen) <= {s['id'] for s in nodes}, 'Unknown/duplicate selected IDs')
        context = render(nodes, set(chosen))
        expected = [{'role': 'system', 'content': SYSTEM},
                    {'role': 'user', 'content': 'DOCUMENTS\n' + context + '\nQUESTION\n' + public['question']}]
        require(request.get('messages') == expected, 'Messages differ from public data/template; regenerate requests')
        method, budget = request.get('method'), request.get('budget')
        require(method in {'full', 'none', 'head', 'bm25', 'neighbors', 'closure'}, 'Unknown method')
        require(type(budget) is int and budget >= 0, 'Invalid context budget')
        if method == 'full':
            require(set(chosen) == {s['id'] for s in nodes} and budget == 0, 'Invalid full-context reference')
        if method == 'none':
            require(not chosen and budget == 0, 'Invalid no-context reference')
        units = request.get('budget_unit')
        if units == 'target_tokenizer':
            count = backend.count_text(context)
        else:
            require(units == 'regex_units_NOT_LLM_TOKENS' and allow_fixture_units and sample['provenance'] == FIXTURE,
                    'Prepare with the target tokenizer; --allow-fixture-units is only for bundled software fixtures')
            count = len(re.findall(r'\w+|[^\w\s]', context))
        require(type(request.get('context_units')) is int and count == request['context_units'],
                'Context count mismatch; prepare again with this tokenizer')
        require(method in {'full', 'none'} or count <= budget, 'Rendered context exceeds budget')


def append_event(path, event):
    with Path(path).open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def journal_state(path, planned_ids):
    started, results = set(), {}
    for event in read_rows(path) if Path(path).exists() else []:
        rid = event.get('id')
        require(rid in planned_ids, 'Journal contains an unknown request ID')
        if event.get('event') == 'started':
            require(rid not in started and rid not in results, 'Duplicate/out-of-order journal start')
            started.add(rid)
        elif event.get('event') == 'result':
            require(rid not in results, 'Duplicate journal result')
            require(event['prediction']['id'] == rid, 'Journal result ID mismatch')
            results[rid] = event['prediction']
        else:
            raise ValueError('Unknown journal event')
    return started, results


def run_batch(requests, backend, out, identity, max_context, max_new, resume=False, preflight_only=False):
    """Backend injection enables failure/recovery tests without simulating real scores."""
    out = Path(out)
    if resume:
        require(out.is_dir() and not preflight_only, 'Resume requires an existing inference directory')
    else:
        out.mkdir(parents=True, exist_ok=False)
    lock = out / '.running.lock'
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError('Run is locked. If the previous process has stopped, preserve the journal and remove only .running.lock before --resume.') from exc
    os.close(descriptor)
    try:
        signature = digest({'identity': identity, 'requests': requests, 'backend': backend.metadata,
                            'max_context': max_context, 'max_new': max_new, 'preflight_only': preflight_only})
        manifest_path = out / 'run_manifest.json'
        if resume:
            manifest = strict_json(manifest_path.read_text(encoding='utf-8'))
            require(manifest['signature'] == signature, 'Resume fingerprint changed; use a new output directory')
        else:
            manifest = {'run_id': uuid.uuid4().hex, 'signature': signature, 'created_utc': utc_now(),
                        'identity': identity, 'backend': backend.metadata,
                        'request_count': len(requests), 'max_context_tokens': max_context,
                        'max_new_tokens': max_new, 'mode': 'preflight' if preflight_only else 'inference',
                        'status': 'PREPARING', 'retry_policy': 'never; interrupted requests become failures'}
            save_json(manifest_path, manifest)
            write_jsonl(out / 'requests.jsonl', requests)
        prepared, preflight = {}, []
        for request in requests:
            row = {'id': request['id'], 'request_sha256': digest(request)}
            try:
                tokens = backend.encode(request['messages'])
                require(isinstance(tokens, list) and bool(tokens) and all(type(t) is int for t in tokens), 'Chat template did not return a nonempty token ID list')
                row.update(input_tokens=len(tokens), prompt_token_sha256=digest(tokens),
                           status='ready' if len(tokens) + max_new <= max_context else 'context_overflow')
                if row['status'] == 'ready':
                    prepared[request['id']] = tokens
            except Exception as exc:
                row.update(status='template_error', error=f'{type(exc).__name__}: {exc}')
            preflight.append(row)
        write_jsonl(out / 'preflight.jsonl', preflight)
        if preflight_only:
            manifest.update(status='PREFLIGHT_ONLY_NO_GENERATION', counts=dict(Counter(r['status'] for r in preflight)))
            save_json(manifest_path, manifest)
            return manifest
        journal = out / 'journal.jsonl'
        started, results = journal_state(journal, {r['id'] for r in requests})
        for request in requests:
            if request['id'] in results:
                previous = results[request['id']]
                require(previous.get('request_sha256') == digest(request)
                        and previous.get('run_id') == manifest['run_id'], 'Journal prediction fingerprint mismatch')

        def record(request, status, **fields):
            prediction = {'id': request['id'], 'run_id': manifest['run_id'],
                          'request_sha256': digest(request), 'status': status,
                          'output': None, 'raw_text': None, 'recorded_utc': utc_now(), **fields}
            append_event(journal, {'event': 'result', 'id': request['id'], 'prediction': prediction})
            results[request['id']] = prediction

        for request, check in zip(requests, preflight):
            rid = request['id']
            if rid in results:
                continue
            if rid in started:
                record(request, 'interrupted_not_retried')
            elif check['status'] != 'ready':
                record(request, check['status'], input_tokens=check.get('input_tokens'), error=check.get('error'))
        pending = [r for r in requests if r['id'] not in results]
        if pending:
            load_start = time.perf_counter()
            try:
                backend.load()
            except Exception as exc:
                for request in pending:
                    record(request, 'backend_load_error', error=f'{type(exc).__name__}: {exc}')
                pending = []
            manifest['model_load_ms'] = 1000 * (time.perf_counter() - load_start)
            manifest['runtime'] = getattr(backend, 'runtime', {})
            manifest['status'] = 'RUNNING'
            save_json(manifest_path, manifest)
        for request in pending:
            rid = request['id']
            append_event(journal, {'event': 'started', 'id': rid, 'at_utc': utc_now()})
            try:
                response = backend.generate(prepared[rid])
                parsed = parse_output(response['raw_text'])
                record(request, 'completed' if parsed is not None else 'invalid_output',
                       output=parsed, input_tokens=len(prepared[rid]), **response)
            except Exception as exc:
                record(request, 'generation_error', input_tokens=len(prepared[rid]), error=f'{type(exc).__name__}: {exc}')
        # A crash before export loses no committed result: --resume reconstructs this file.
        write_jsonl(out / 'predictions.jsonl', [results[r['id']] for r in requests])
        manifest.update(status='FINISHED' if all(r['status'] == 'completed' for r in results.values())
                               else 'FINISHED_WITH_FAILURES', finished_utc=utc_now(),
                        counts=dict(Counter(r['status'] for r in results.values())))
        save_json(manifest_path, manifest)
        return manifest
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('config', 'data', 'requests', 'out'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--max-requests', type=int, default=10, help='First N planned requests; default 10; explicit cap, never all by accident')
    parser.add_argument('--preflight', action='store_true', help='Tokenize/check inputs; do not load weights or generate')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--allow-fixture-units', action='store_true')
    args = parser.parse_args()
    require(args.max_requests > 0, '--max-requests must be positive')
    config = load_config(args.config)
    samples = read_rows(args.data)
    validate_dataset(samples)
    requests = read_rows(args.requests)
    backend = HFBackend(config)
    # Validate the entire prepared file before selecting the explicit smoke-run subset.
    verify_requests(requests, samples, backend, args.allow_fixture_units)
    chosen = requests[:args.max_requests]
    identity = {'config': config, 'dataset_file_sha256': file_sha256(args.data),
                'prepared_requests_file_sha256': file_sha256(args.requests),
                'max_requests': args.max_requests, 'allow_fixture_units': args.allow_fixture_units,
                'code_sha256': {name: file_sha256(Path(__file__).with_name(name))
                                for name in ('run_local.py', 'prototype.py', 'validate_data.py')},
                'warning': 'Fixture data/regex budgets cannot establish research performance.'
                           if any(s['provenance'] == FIXTURE for s in samples) else None}
    result = run_batch(chosen, backend, args.out, identity, config['max_context_tokens'],
                       config['max_new_tokens'], args.resume, args.preflight)
    print(json.dumps({key: result[key] for key in ('run_id', 'status', 'request_count', 'counts')}, indent=2))


if __name__ == '__main__':
    main()
