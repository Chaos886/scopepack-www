# Reproducibility status

The offline prototype and seven software checks are reproducible with Python 3.10+ and the standard library. Run the commands in the repository README from its root.

The bundled eight cases are hand-constructed software fixtures. Prepared requests in demo_run have not been sent to a model. No model-quality or token-efficiency results are claimed.

For real experiments, pin the dataset, model, tokenizer, prompt, decoding settings and dependency predictor; retain raw outputs, failures, token usage and timing. Keep gold labels outside model inputs.
