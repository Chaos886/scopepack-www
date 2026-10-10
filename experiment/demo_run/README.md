# Prepared fixture requests — not model results

Status: PREPARED_NOT_EXECUTED. These 112 requests come from eight hand-constructed software fixtures. They have not been sent to any LLM.

- requests.jsonl contains public model inputs.
- context_diagnostics.jsonl contains evaluation-only evidence retention diagnostics; never send it to the answer model.
- manifest.json records the preparation status and input/code hashes.

Budgets use regex_units_NOT_LLM_TOKENS, not a real model tokenizer. These files cannot support empirical accuracy or token-efficiency claims.
