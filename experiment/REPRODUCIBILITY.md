# Reproducibility status

The offline selector, evaluator, paired analysis, data validator and journal core are reproducible with Python 3.10+ and the standard library. All 27 software tests passed on 2026-10-10: 7 selection/scoring, 6 analysis, 9 execution/recovery and 5 data-validation tests. Tests use artificial fixtures or a fake backend and do not measure language-model performance.

The local Hugging Face adapter in run_local.py is implemented but **has not been validated with real model weights**. The current environment has no torch/transformers or configured model. Follow [LOCAL_INFERENCE.md](LOCAL_INFERENCE.md) to establish an actual model environment, verify compatibility and then freeze package versions. There is no tested inference dependency lock yet.

The eight bundled cases are hand-constructed software fixtures. demo_run is the original offline prepared snapshot with its original code hash; it has not been sent to a model. Generate a new prepared directory for current code or a real tokenizer. No model-quality, token-efficiency or end-to-end speed results are claimed.

Real experiments must preserve the data, local model/tokenizer file hashes, chat template, configuration, decoding settings, dependency predictor, raw generated token IDs/text, errors, token counts and timings. The local runner records these execution artifacts and rejects changed resume identities. Gold labels remain outside model inputs. Structure and hash validation do not certify semantic annotation quality, licensing or near-duplicate removal.
