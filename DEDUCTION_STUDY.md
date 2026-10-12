# Proposed controlled deduction study

Status: executable diagnostic protocol; no language-model results. This supplement is intended for integration into the evaluation section after real experiments. The existing manuscript and LaTeX submission draft have not yet incorporated empirical findings from this study.

## Research question and scope

We study whether context compression preserves the facts and rules required for a model to solve a specified deductive task. The diagnostic separates evidence loss during compression from task failure when a sufficient proof remains available. It does not identify the model's internal reasoning algorithm or establish broad logical competence.

The formal fragment consists of finite ground facts and conjunctive forward rules over signed atoms. Explicit negation is represented separately from the absence of a derivation. Rules are directional: converse reasoning, contraposition, default negation, quantifiers and disjunction are outside this protocol. Inconsistent theories are rejected. A query is entailed if its literal is derivable, contradicted if its explicit negation is derivable, and unknown otherwise. These labels refer to the specified operational semantics, not unrestricted classical first-order entailment.

## Construction and validation

The initial development suite contains 60 synthetic questions: four lexical/order families, five template depths from zero through four, and three matched worlds per family-depth combination. Depth zero is a direct-reading control. The other levels require conjunctive rule applications distributed across three constructed documents. Counterfactual worlds change the reachable terminal polarity and an unreachable distractor consequent; unknown worlds replace an essential starting fact with an irrelevant fact. These worlds are matched controls rather than strict single-token interventions.

Unsupported cycles, converse traps, explicit negative premises and mentions of both query polarities prevent several simple mention-based shortcuts. This construction does not rule out other template artifacts. Lexical reseeding is not template generalization, and all bundled examples are designated development data. Families group their variants for statistical analysis; only four clusters are available, which is inadequate for strong uncertainty claims. Future evaluation must introduce independently designed templates and natural Web cases.

A symbolic forward solver enumerates subset-minimal sufficient evidence sets and computes minimum rule depth, where a fact has depth zero and a rule has depth one plus the maximum depth of its premises. Unknown queries have no proof depth. Every natural-language sentence and query is checked against an exact controlled-language rendering of its evaluation-side symbolic annotation. Enumeration limits fail explicitly. The metadata and gold proofs are excluded from the selector and answer-model input; this track therefore supplies no oracle edges to ScopePack.

## Outcomes and controls

All methods use identical answer instructions and generation settings. Full context measures task performance before compression; no context diagnoses answer priors and protocol behavior. BM25 selection, neighbor expansion and the current dependency closure selector use the same input documents and declared rendered-context budgets. Real experiments must use the target tokenizer, retain chat-template/output-window checks, and include the established strong pruning baselines before drawing comparative conclusions.

The primary outcome is accuracy against the complete original theory, with planned missing or invalid responses retained as failures. Three-label macro accuracy and label confusion expose degenerate strategies such as always abstaining. Paired-world accuracy requires all three associated outcomes to be correct and reports incomplete triplets separately.

For originally answerable queries, proof retention measures whether the retained sentences still derive the correct literal. We additionally report accuracy conditional on a retained proof and the proportion of originally answerable queries answered correctly with a formally sufficient citation set. The latter accepts valid alternative proofs and redundant evidence; it is a support measure, not citation minimality or a transcript of hidden reasoning. Unknown queries are excluded from positive-proof denominators. Scores against the visible compressed theory are secondary: appropriate abstention after losing a premise does not count as success on the original task.

Conditional accuracy has method-dependent denominators and must not be interpreted as an unbiased causal comparison of model reasoning. Retained-proof failures may also arise from formatting, citation, protocol or infrastructure errors. Main method comparisons should use the same complete set of planned questions, retain failures, and apply paired cluster analysis. The current diagnostic report adds descriptive breakdowns; the existing bootstrap tool covers answer exact match and the exact-evidence proxy, not the new proof-support metrics.

## Claims and external validity

The expected contribution of this study is a falsifiable mechanism diagnostic for evidence-preserving compression, contingent on future measurements. RuleTaker and ProofWriter exemplify established controlled rule-reasoning evaluation; the present implementation is not claimed to be the first deductive benchmark or an official reproduction of those datasets. Broader tasks and natural Web evidence remain necessary for external validity. No accuracy, significance, latency benefit or superiority is asserted before model outputs and strong-baseline comparisons are obtained.

Implementation and executable commands: [experiment/DEDUCTION.md](experiment/DEDUCTION.md).
