# Preserving Applicability under Context Budgets: Dependency-Closed Compression for Web Question Answering

Anonymous working draft · October 10, 2026 · Version 0.1

*Readable mirror of `www_draft.tex`; keep both copies synchronized when editing. This is not a verified ACM submission layout.*

**Research status.** This manuscript specifies a proposed method and an evaluation protocol. The accompanying offline prototype has no LLM inference results. All empirical result cells are explicitly pending. Novelty, real-data effectiveness, and submission-format compliance remain to be established.

## Abstract

Web question answering often depends on the scope of a statement: which users it covers, when it applies, and which source supports it. Under a restricted context budget, selecting a highly relevant statement without its applicability conditions can change the meaning of the retained evidence. We study this problem as dependency-closed context compression. We propose ScopePack, an extractive packing procedure that augments sentence relevance with directed dependencies on qualifiers, antecedents, and explicit source references. A selected statement is packed together with its predicted dependency closure, while provenance and serialization overhead are included in the budget. We specify a controlled evaluation that holds retrieval and answer generation fixed and distinguishes answer correctness, evidence sufficiency, and compression-induced damage. Particular attention is given to strong sentence-pruning and neighbor-expansion baselines, dependency-prediction errors, and total system cost. This draft includes a deterministic prototype and software checks; it does not yet establish an empirical improvement over existing methods. The proposed study asks whether applicability-aware packing offers a useful quality--cost trade-off beyond contextual sentence pruning.

**Keywords:** context compression; retrieval-augmented generation; Web question answering; evidence dependencies; applicability.

## Introduction

Web information is frequently conditional. A product price may apply only to new accounts, a refund rule may exclude reseller purchases, and an updated policy may coexist with archived copies. An answer grounded in these materials requires more than finding a sentence that mentions the requested attribute. It requires preserving the conditions under which that sentence can be used.

Consider two sentences in a service policy: “The annual plan offers a refund within fourteen days” and “This refund applies only to direct purchases and excludes reseller purchases.” For a question about reseller purchases, retaining the first sentence alone supports an overgeneralized answer. Both sentences are relevant to the decision, but the second may have weaker surface overlap with the query. This is a constructed motivating example, not an observation about the frequency of failures in deployed systems.

Prompt compression and context pruning reduce the material presented to an answer model. LongLLMLingua uses question-aware compression, adaptive budgets, and related mechanisms [LongLLMLingua](https://arxiv.org/html/2310.06839v2). LLMLingua-2 trains an efficient extractive classifier [LLMLingua-2](https://arxiv.org/html/2403.12968v2). Provence contextualizes sentence selection and integrates pruning with reranking [Provence](https://arxiv.org/html/2501.16214v1). These methods make a substantial part of the proposed design space established prior work. In particular, contextual selection can already retain related sentences implicitly. A credible contribution must therefore demonstrate a benefit beyond relevance scoring, sentence boundaries, and simply expanding the local context.

We investigate a narrower question: *does explicitly enforcing predicted applicability dependencies improve evidence-grounded answers at a fixed serialized context budget?* We represent a candidate sentence and its required qualifiers as a dependency closure. The unit of packing becomes this closure rather than an independently scored sentence. The answer model receives unmodified text and source identifiers; it does not receive a generated reasoning chain or a claim that the selected material is guaranteed sufficient.

The proposed contribution has three parts. First, we formalize budgeted extractive selection with directed dependency constraints and clarify the difference between structural feasibility and semantic sufficiency. Second, we specify an implementable packing algorithm that uses the same relevance scores as its ablations. Third, we design a falsifiable evaluation that measures answer quality, complete evidence retention, and damage to previously correct answers, including paired changes to applicability conditions. These are design contributions in this version. Their practical value must be established by the experiments described below.

The Web setting is central to the intended evaluation. Sources may duplicate or contradict one another, page publication time need not equal policy validity time, and source provenance has a real token cost. We begin with frozen textual snapshots to isolate compression from retrieval drift and browser interaction. This scope does not support claims about autonomous Web navigation, live freshness, or multimodal document understanding.

## Related Work and Positioning

**Long-context evaluation.**

LongBench standardizes diverse long-context tasks and provides task-specific prompts and metrics [LongBench](https://arxiv.org/html/2308.14508v2). Its original release includes 21 datasets across six task categories. It provides a useful external evaluation backbone, but its answer metrics alone cannot establish whether a compressed context preserves every condition needed for a grounded answer. Our proposed diagnostic slice supplements such evaluation; it is not presented as a replacement for LongBench or as a completed new benchmark.

**Extractive prompt compression.**

LongLLMLingua already studies question-aware coarse-to-fine compression, document reordering, dynamic allocation, and subsequence recovery [LongLLMLingua](https://arxiv.org/html/2310.06839v2). LLMLingua-2 obtains extractive labels by distillation and trains a bidirectional token classifier [LLMLingua-2](https://arxiv.org/html/2403.12968v2). Extraction limits invented surface text, but deleting a qualifier can still change the interpretation of a retained statement. This logical possibility motivates an experiment; it does not establish that any specific baseline systematically fails on our target tasks.

**Contextual sentence pruning.**

Provence is the closest directly inspected sentence-pruning comparator [Provence](https://arxiv.org/html/2501.16214v1). It jointly encodes the query and context, can select varying numbers of sentences, and uses sentence rounding to avoid partial selections. Its discussion explicitly recognizes semantically connected sentences. Consequently, the claim that previous pruning methods all treat sentences independently would be inaccurate. We instead test whether an explicit dependency constraint provides incremental value when relevance scores, budgets, and answer models are controlled. RECOMP, FilCo, DSLR, and other recent pruning methods also require direct review and appropriate inclusion before submission; their discussion here is limited to their positioning in Provence.

**Structured retrieval and reasoning graphs.**

AutoPrunedRetriever represents evidence using compact entity--relation structures, retrieves reasoning paths, and describes reuse of previously constructed reasoning subgraphs [AutoPrunedRetriever](https://arxiv.org/html/2602.04926v1). It demonstrates that graph-based compression and compact reasoning structure are not new categories. Our proposed scope is fixed-candidate, extractive context packing with applicability constraints and explicit source spans. This difference in setting is not sufficient by itself to establish novelty or superiority. A direct comparison, or a carefully justified setting mismatch, is required.

**Positioning boundary.**

We do not claim the first use of evidence graphs, query-aware compression, dynamic token allocation, or citations. The candidate distinction is the combination of directed applicability closure, exact serialized budget enforcement, and a paired diagnostic protocol that tests the consequences of breaking such dependencies. A full review of relevant 2025--2026 work remains a submission prerequisite.

## Problem Definition

Let $q$ be a question, $D$ a fixed set of retrieved document snapshots, and $V=\{s_1,\ldots,s_m\}$ the candidate sentence units. Every unit has a stable identifier, document membership, paragraph location, and original text. A selected set $S\subseteq V$ is serialized as $Z=\operatorname{Render}(S)$, preserving source order within each document. Titles, provenance markers, separators, and displayed snapshot metadata are included in $Z$.

For a target model tokenizer $\tau$, the context cost is

$$
 c_\tau(S)=|\operatorname{Tok}_\tau(\operatorname{Render}(S))|.
$$

The context budget $B$ excludes the fixed question and instructions, whose lengths are logged separately. Before generation, the complete chat-template input plus the reserved output allowance must fit the model window. No silent truncation is permitted.

A directed edge $(i,j)\in\widehat E$ means that using $s_i$ requires retaining $s_j$ under the dependency predictor. Dependencies may encode an applicability condition, an antecedent, or an explicit cross-document reference. Edges express a retention requirement, not semantic entailment, source trust, or causal truth. Define

$$
 \operatorname{cl}_{\widehat E}(S)=S\cup\{s_j:\exists s_i\in S,\ i\leadsto_{\widehat E}j\}.
$$

A set is dependency-closed if $\operatorname{cl}_{\widehat E}(S)=S$. The distinction between the predicted graph $\widehat E$ and independently annotated dependencies $E^*$ is maintained throughout evaluation.

With nonnegative relevance scores $r_i$, we study

$$
\begin{aligned}
 \max_{z\in\{0,1\}^m}\quad &\sum_{i=1}^{m}r_i z_i \\
 \text{subject to}\quad &z_i\le z_j\quad\forall(i,j)\in\widehat E,\\
 &c_\tau(\{s_i:z_i=1\})\le B.
\end{aligned}
$$

This objective is a selection surrogate, not an answer-quality guarantee. A qualifier can receive little direct relevance and still be retained through a dependency.

The graph encodes conjunctive requirements. Multiple interchangeable supporting passages cannot be represented by simply adding an edge to each alternative, since that would unnecessarily require all alternatives. In the initial method, uncertain or alternative support is not converted into a hard dependency. Extending the representation to disjunctive evidence bundles is future work. Evaluation annotations may nevertheless contain multiple sufficient evidence sets.

## The Proposed Method

### Source-Preserving Units

Document parsing produces sentences with stable IDs and paragraph membership. Source headers are emitted once per selected document. Reordering is disabled for the main controlled experiment, so that improvements cannot be attributed to moving evidence toward the beginning. All methods share the same source metadata where their output format allows it. A budget audit is applied after final serialization.

Table headers and list scopes can carry dependencies analogous to sentence qualifiers. Their treatment requires a structure-preserving parser; the current prototype accepts presegmented text and does not implement general HTML or table parsing. Claims about tables must therefore await that extension and a dedicated evaluation.

### Dependency Construction

The accompanying prototype implements a transparent, English-only rule system. It binds a paragraph when it contains explicit applicability markers such as “only,” “unless,” “except,” or “effective.” It resolves literal sentence-ID references already present in input text and uses a small demonstrative/pronoun rule to retain a preceding sentence in the same paragraph. It does not consume gold answers, evidence sets, task-type annotations, or human dependency labels.

These rules are intentionally conservative and can overbind a paragraph. Their role is to provide an executable starting point and an inspectable error source. They do not establish that natural-language dependencies have been solved. Reference markers in the bundled constructed examples are artificial software fixtures, not a realistic substitute for cross-page reference resolution.

For real-data experiments, we propose a typed relation predictor over candidate sentence pairs. Candidate pairs can be limited to the same paragraph, adjacent paragraphs, explicit references, and entity-linked passages. A predictor returns a relation label, a confidence score, and existing span IDs. Only IDs present in the input are accepted. Confidence thresholds are selected on development data, separately by relation type when supported by enough annotations. Low-confidence predictions remain unbound; they are not silently promoted to hard constraints.

If a learned predictor is pursued, one possible training objective is cross-entropy over relation types including “no dependency.” Training data must contain negative pairs that are topically related but do not impose a joint-retention requirement. Held-out evaluation reports edge precision and recall and, more importantly, closure size inflation and missing necessary closures. Human dependency graphs are used only as diagnostic oracles. No learned predictor is trained in this draft.

### Budgeted Closure Packing

For each candidate $s_i$, compute its closure $K_i=\operatorname{cl}_{\widehat E}(\{s_i\})$. Starting from a feasible closed set $S$, consider $S\cup K_i$. Its marginal relevance and cost are

$$
\begin{aligned}
 \Delta R_i &= \sum_{s_j\in K_i\setminus S}r_j,\\
 \Delta c_i &= c_\tau(S\cup K_i)-c_\tau(S).
\end{aligned}
$$

Among feasible additions with positive gain, select the one maximizing $\Delta R_i/\max(1,\Delta c_i)$. Recompute cost on the fully rendered candidate rather than summing isolated sentence lengths. Shared headers and tokenizer boundary effects make such a sum unreliable.

The greedy procedure may miss a valuable large bundle after accepting small ones. The prototype therefore uses bounded multistart: one empty start and feasible closures seeded by the eight highest-scoring sentences. Each start is greedily completed; the feasible outcome with highest total relevance is returned. Ties favor lower cost and then a deterministic ID ordering. The same multistart policy is used by relevance-based baseline selectors, preventing an optimizer advantage from being attributed to dependencies.

An oversized closure is skipped. The method never breaks a hard dependency merely to fill remaining space. If no positive-gain bundle fits, it returns empty context; the answer model is then expected to handle missing evidence under the same answer protocol as all other methods. This behavior may lose useful partial evidence and must be measured, especially at tight budgets.

| Step | Operation |
|---|---|
| 1 | Parse public inputs into ordered source spans. |
| 2 | Compute relevance and predict directed dependencies. |
| 3 | Form closures for every candidate span. |
| 4 | Generate empty and bounded seeded starts. |
| 5 | Add the feasible closure with best marginal density. |
| 6 | Return the best rendered, budget-checked outcome. |

*Table 1. ScopePack packing procedure. Dependency prediction and tokenization are charged to system cost.*

### What the Constraint Guarantees

**Proposition 1.** If every initial set is closed under $\widehat E$, and every update unions it with a closure $K_i$ only when the rendered result meets budget $B$, the returned set is closed under $\widehat E$ and has cost at most $B$.

*Proof.* Every start is empty or a feasible closure. The union of two closed sets is closed: a dependency successor of any included node belongs to the closed set that included that node. Every accepted update is explicitly budget-checked. Induction establishes both properties for each trajectory; selecting one completed trajectory preserves them. □

This proposition is structural. It does not imply semantic fidelity, complete evidence, factual correctness, or optimality of the packing objective. Missing predicted edges can leave necessary conditions absent. Spurious edges can consume the budget. The method is a heuristic for a constrained selection problem and has no claimed approximation ratio.

### Implementation Boundary

The current relevance scorer is a simple sentence-level BM25 implementation. The main scientific comparison should also use frozen strong contextual scores, including a Provence-based variant where appropriate. The prototype has no trained encoder, neural compressor adapter, Web crawler, or inference backend. It prepares requests and evaluates imported model predictions. Its default length counter uses regex units solely for offline checks. Formal experiments require the target tokenizer; regex-unit budgets must never be reported as model-token efficiency.

## Evaluation Protocol

### Research Questions

**RQ1: Quality.** At matched context budgets, does predicted dependency closure improve answer correctness and evidence-supported correctness over strong contextual pruning and neighbor expansion?

**RQ2: Mechanism.** Are any gains concentrated on applicability-dependent questions, and do they persist after controlling for relevance scores, context length, and sentence order?

**RQ3: Robustness.** How do graph errors, source shifts, paraphrasing, evidence position, and tighter budgets change outcomes?

**RQ4: Efficiency.** Does the improvement survive the cost of parsing, dependency prediction, packing, and answer generation, including cold and reusable preprocessing regimes?

### Data and Splits

We propose three complementary evaluation layers. First, established multi-document QA tasks provide external comparability: the HotpotQA, 2WikiMultihopQA, and MuSiQue subsets of LongBench are starting candidates. Results on these subsets are labeled as subset results rather than the complete benchmark. Original dataset versions and LongBench adaptations are not mixed.

Second, a natural Web snapshot slice targets temporal applicability, eligibility conditions, exceptions, provenance, and source disagreement. An initial annotation pilot of approximately 150 questions is proposed; the formal sample size will be determined using pilot variance, cluster structure, and the minimum effect worth detecting. No such real-data slice has been collected in this version. Source licenses and redistribution conditions must be recorded before release.

Third, a separately reported controlled slice contains paired examples that differ in one answer-determining condition. Variants may change an eligibility clause, effective date, or exception while preserving unrelated content. Annotators verify both versions for coherence and answerability. Such interventions diagnose sensitivity; they are not used to estimate the natural prevalence of a failure.

Each example includes the question, source snapshots, answer aliases or structured answer fields, one or more sufficient evidence sets, answerability, and an event/document cluster ID. Two annotators independently verify development and test labels; disagreements are adjudicated. The annotation protocol distinguishes publication time, snapshot time, and validity time. It does not assume that the latest page or an official-looking source is necessarily correct.

All variants, near-duplicate pages, and questions about the same underlying event belong to one split. A development split is used for thresholds, prompts, and format decisions. The locked test split is used for final comparisons. Test evidence annotations never enter compression or generation. A no-context baseline and answer-changing interventions probe prior-knowledge shortcuts; they cannot certify absence of pretraining contamination.

### Comparators and Controlled Conditions

The required baselines are full context, no context, head/head-tail truncation, BM25 or dense sentence selection, a strong contextual reranker, neighbor-expanded selection, query-focused summarization, LongLLMLingua, LLMLingua-2, and Provence. Implementations must be pinned and described. Other contemporaneous close methods identified in the literature audit must be added when applicable.

For the decisive ablation, use identical sentence scores, serialization, ordering, tokenizer, and selection procedure with and without dependency edges. Neighbor expansion includes the preceding and following sentence within a document, under the same budget; it is the principal inexpensive alternative explanation. Oracle dependencies and gold-evidence-only contexts are diagnostic references, not deployable methods or mathematical performance upper bounds.

Budget settings of 512, 1,024, 2,048, and 4,096 target-model tokens are proposed for sufficiently long inputs. Actual token distributions, unused capacity, and constraint violations are reported. Full context is an additional operating point, not a matched-budget competitor. A method whose native threshold exceeds budget must use a documented budget adapter, tuned only on development data. Its native quality--cost frontier should also be reported to avoid an unfair adapter-induced disadvantage.

We propose at least two answer-model families, including a reproducible open-weight model and a stronger available model if resources permit. Exact versions, chat templates, decoding and reasoning settings, output allowances, batching, hardware, and caching policy remain to be filled before execution. No particular current model availability or price is assumed. Independent questions use independent sessions. Infrastructure retries follow a fixed policy; retries after an incorrect answer are not allowed unless explicitly part of a separately budgeted method.

### Metrics

**Answer quality.**

Established datasets use their official metrics and answer-extraction conventions. For a new short-answer slice, define correctness $A_i\in\{0,1\}$ using explicit aliases or typed numeric/unit fields. Negation, units, punctuation with semantic significance, and version numbers must not be removed by indiscriminate normalization. Information-insufficient questions are evaluated for correct abstention and reported separately.

**Complete evidence retention.**

For answerable question $i$, let $\mathcal G_i$ contain independently annotated sufficient sets of source spans. For an extractive selected set $S_i$, define

$$
 \mathrm{CER}_i=\max_{G\in\mathcal G_i}\mathbf{1}[G\subseteq S_i].
$$

This measures whether at least one complete annotated set survives. It is distinct from token overlap and from final answer correctness. Incomplete annotation can underestimate sufficiency. Abstractive compressors need a semantic support audit; ID-based CER cannot be blindly applied to them.

**Evidence-supported answers.**

Define $E_i=1$ when the supplied citations jointly support the answer and cover the required applicability conditions, with unsupported additional citations penalized under a fixed rubric. The primary proposed joint score is $100\,\mathbb{E}[A_iE_i]$. Semantic citation support requires human assessment or an independently calibrated evaluator. The prototype instead implements a strict exact-evidence-set proxy: citations must match one annotated sufficient set and must be visible in the actual compressed input. This proxy can reject valid alternate citations and is not presented as semantic entailment evaluation.

**Compression-induced damage and rescue.**

Let $A_i^F$ and $A_i^C$ denote correctness with full and compressed contexts. Report both the full-to-compressed transition table and

$$
 \mathrm{Damage}=\frac{\sum_i\mathbf{1}[A_i^F=1,A_i^C=0]}{\sum_i\mathbf{1}[A_i^F=1]}.
$$

Rescue is defined analogously conditional on $A_i^F=0$. A zero denominator is reported as undefined. These paired descriptive statistics do not isolate information loss from stochastic generation unless decoding variability is controlled or replicated.

**Efficiency.**

Report context tokens, total request tokens, generation tokens, compression latency, time to first token, total latency, and hardware memory where measurable. Total time includes parsing, dependency prediction, packing, and answering. External retrieval can be excluded only in the explicitly fixed-candidate setting and must then be reported separately for an end-to-end deployment study. Query-independent preprocessing may be amortized over a stated reuse count; query-dependent work may not. Both batch size one and throughput settings are useful, but must not be mixed.

### Analysis and Statistical Plan

The primary paired comparison is ScopePack versus the strongest development-selected same-score baseline at a preselected budget. We report mean differences with cluster-bootstrap confidence intervals, sampling document/event clusters with all their question variants together. Seed variability is separate from dataset sampling uncertainty. Multiple secondary task/budget comparisons are identified as exploratory or corrected under a declared policy.

Ablations remove qualifier binding, antecedent binding, explicit-reference binding, and all edges. Additional experiments compare predicted versus annotated dependencies, vary confidence thresholds, move necessary qualifiers away from their associated statements, and replace marker vocabulary with paraphrases. A length-matched control addresses the possibility that dependency packing merely retains more text. Errors are coded into absent evidence, wrong dependency, excessive closure, answer-model failure despite adequate evidence, and scoring ambiguity.

The design is falsifiable. If neighbor expansion matches the proposed method, explicit relations may not justify their complexity. If gains disappear with a stronger pruner, the contribution is limited to weaker selection regimes. If dependency prediction erases latency savings, the method may improve grounding but cannot be claimed as an acceleration method. These outcomes must be reported rather than repaired by selecting favorable subsets after inspecting test results.

## Current Evidence and Results to Be Collected

### Completed Artifact Checks

The accompanying program separates public model inputs from evaluation-only annotations, enforces the rendered budget for constrained selectors, handles graph cycles, and preserves missing predictions in scoring denominators. Eight hand-constructed examples cover time scope, exceptions, negation, eligibility, explicit references, missing information, and a simple control. They are software fixtures with synthetic provenance, not sampled Web data. The prepared grid contains 112 requests: two reference settings plus four constrained selectors at three regex-unit budgets for each of eight examples. No requests have been sent to a model.

Software checks test closure feasibility, budget feasibility, invariance to changed gold labels, invalid/invisible citations, malformed outputs, abstention, missing predictions, and duplicate request handling. Passing these checks is evidence about implementation invariants only. It does not establish retrieval quality, compression fidelity, or a benchmark score.

| Method | Answer score | Joint support | CER | Actual tokens | Total latency | Damage |
|---|---|---|---|---|---|---|
| Full context | pending | pending | pending | pending | pending | reference |
| Strong contextual selection | pending | pending | pending | pending | pending | pending |
| Neighbor expansion | pending | pending | pending | pending | pending | pending |
| LongLLMLingua | pending | pending | pending | pending | pending | pending |
| LLMLingua-2 | pending | pending | pending | pending | pending | pending |
| Provence | pending | pending | pending | pending | pending | pending |
| ScopePack (predicted dependencies) | pending | pending | pending | pending | pending | pending |
| ScopePack (annotated dependencies) | pending | pending | pending | pending | pending | pending |

*Table 2. Required empirical results for a fixed model, dataset, and budget. Every pending cell is an experiment not yet executed. Annotated dependencies are an oracle diagnostic; no performance numbers are substituted for model measurements.*

### Required Empirical Evidence

Table 2 is a collection template, not a results table with observations. The first completed study must establish a reliable failure phenomenon on real data. The second must compare quality--cost frontiers under fixed retrieval. The third must isolate dependency prediction from the value of enforcing a correct dependency graph. At least one untouched source/domain evaluation is required before making a generalization claim.

Four figures are planned: joint support versus actual context tokens; quality versus total latency; full-to-compressed answer transitions by task type; and performance versus dependency-prediction error. These figures will be generated only from saved measured records. A qualitative figure should show an original passage, each method's actual retained text, model outputs, and independently adjudicated evidence. Favorable examples should be accompanied by representative failures.

## Limitations and Responsible Data Use

The largest unresolved assumption is that useful dependencies can be predicted cheaply and accurately enough. Hard closure can overconstrain the budget, and the additive relevance objective does not model all benefits of combining evidence. The initial rule system is English-specific and brittle to paraphrases. Cross-document anaphora, tables, implicit temporal scope, competing interpretations, and alternative evidence paths require additional modeling.

All extracted statements may remain verbatim while their combination becomes misleading. Preserving a predicted dependency does not resolve contradiction, establish source authority, or guarantee truthful answers. The answer model may ignore the retained qualifier. The proposed short-answer diagnostic also leaves long-form citation evaluation and future-turn memory outside its scope.

Snapshots must retain source attribution and comply with access and redistribution conditions. Public availability alone does not grant redistribution rights. Potentially sensitive personal information should be excluded or appropriately handled. Web content is passed as untrusted evidence, not executable instructions. A claim of robustness to prompt injection would require a separate security evaluation, which is not provided here.

## Conclusion

We have specified dependency-closed extractive compression as a way to test whether preserving applicability conditions improves grounded Web question answering under context budgets. The current artifact provides an executable offline selector, scoring scaffold, and explicit evaluation design. Whether this approach outperforms contextual pruning and neighbor expansion, and whether any quality benefit justifies its cost, remain open empirical questions. The next stage is a locked real-data pilot followed by controlled model experiments; conclusions and contribution language must then be rewritten to reflect the observed evidence.

## References

1. Yushi Bai et al. LongBench: A Bilingual, Multitask Benchmark for Long Context Understanding. Inspected version: [arXiv:2308.14508v2](https://arxiv.org/html/2308.14508v2).
2. Huiqiang Jiang, Qianhui Wu, Xufang Luo, Dongsheng Li, Chin-Yew Lin, Yuqing Yang, and Lili Qiu. LongLLMLingua: Accelerating and Enhancing LLMs in Long Context Scenarios via Prompt Compression. Inspected version: [arXiv:2310.06839v2](https://arxiv.org/html/2310.06839v2).
3. Zhuoshi Pan et al. LLMLingua-2: Data Distillation for Efficient and Faithful Task-Agnostic Prompt Compression. Inspected version: [arXiv:2403.12968v2](https://arxiv.org/html/2403.12968v2).
4. Nadezhda Chirkova, Thibault Formal, Vassilina Nikoulina, and Stéphane Clinchant. 2025. Provence: efficient and robust context pruning for retrieval-augmented generation. ICLR. Inspected version: [arXiv:2501.16214v1](https://arxiv.org/html/2501.16214v1).
5. Ning Wang, Kuanyan Zhu, Daniel Yuehwoon Yee, Yitang Gao, Shiying Huang, Zirun Xu, and Sainyam Galhotra. 2026. Pruning Minimal Reasoning Graphs for Efficient Retrieval-Augmented Generation. Inspected version: [arXiv:2602.04926v1](https://arxiv.org/html/2602.04926v1).

---

Appendices
## Reproducibility Record

Every run must record dataset revision, split manifest, source-cluster ID, public-input hash, model revision, tokenizer revision, chat template, prompt version, compression configuration, selected spans, serialized input, actual token count, decoding configuration, raw output, parsed answer, citations, error status, retries, usage, and timing. Output files are append-safe or uniquely named, and prediction IDs must map to the saved request manifest. The prototype rejects duplicate or unknown prediction IDs and input-hash mismatches; missing predictions receive zero rather than disappearing from the denominator.

The generation runner remains to be connected to an authorized model endpoint or local checkpoint. It must record exact model identifiers and must not silently substitute models. Supported decoding arguments vary by backend. The final request length must be checked after applying the model's chat template. Infrastructure failures, budget failures, malformed outputs, and semantic errors should be distinguishable in analysis even when they all count as task failures.

## Annotation Instructions

Annotators first answer using the complete source bundle. They then identify at least one sufficient evidence set, including qualifiers and cross-document bridges that materially determine the answer. Alternative sufficient sets are recorded when discovered. A useful check is to remove a suspected qualifier and ask whether the remaining material permits a materially different interpretation. This is an annotation aid, not proof of logical necessity in all contexts.

For temporal cases, annotators mark the time requested by the question and the validity interval expressed in the evidence. For conditional cases, they identify the population and exception. For contradictory sources, they record whether the task supplies a resolution rule. If it does not and the evidence remains ambiguous, the correct label may be abstention or an explicit conflict answer. Task design must not force a unique answer that the sources do not support.

## Submission Conversion Checklist

This source uses a standalone two-column article layout for editing and compilation. It is not a verified ACM template. Before submission, confirm the intended WWW edition, track scope, current format and page limit, anonymity rules, supplementary-material rules, and applicable AI-use disclosure policy from the official call. Convert to the required ACM class, complete bibliographic metadata from canonical records, and audit author-identifying paths and artifact links. The pending-result table and research-status box may be removed only after the corresponding evidence exists and the manuscript has been revised accordingly.
