# Next research milestones

## 1. Establish a viable research question

- [ ] Complete direct review of RECOMP, FilCo, DSLR, COMPACT and close 2025–2026 work.
- [ ] Specify the novelty boundary against Provence and graph-based retrieval/compression.
- [ ] Confirm the intended WWW edition, track, submission rules and deadline from its CFP.

## 2. Build a real-data pilot

- [ ] Collect licensed, frozen Web snapshots; retain source and validity metadata.
- [ ] Define annotation rules and sufficient evidence sets; independently verify labels.
- [ ] Keep source/event clusters and all paired variants in one split.
- [ ] Pilot approximately 150 questions, with development decisions separated from evaluation.

## 3. Connect real inference

- [ ] Choose exact model versions, available resources and spending limits.
- [ ] Pin tokenizer and chat template; check complete request length before generation.
- [ ] Connect the backend; preserve raw outputs, failures, usage and latency.
- [ ] Validate ten requests end to end before increasing run size.

## 4. Test the mechanism

- [ ] Implement Provence and other required strong comparators.
- [ ] Compare identical scores/optimizer with and without dependency edges.
- [ ] Compare neighbor expansion and annotated versus predicted dependency graphs.
- [ ] Measure actual token budgets, complete evidence retention, answer scores and failures.
- [ ] Add independent semantic support auditing and cluster-bootstrap intervals.
- [ ] Include compression and graph-prediction cost in total system measurements.

## 5. Decide whether to scale and submit

- [ ] Stop or revise the hypothesis if a strong baseline or neighbor expansion explains the gain.
- [ ] Lock the formal test split and analysis before final comparisons.
- [ ] Rewrite contributions and conclusions around observed evidence, including failures.
- [ ] Convert to the required ACM template and verify anonymity and artifact rules.

None of the unchecked items is claimed complete. The repository currently provides the draft and offline scaffold only.
