---
paths:
  - "services/**/harness/**"
  - "services/**/evolution/**"
  - "services/**/agent/**"
  - "services/**/evals/**"
  - "services/**/models/**"
  - "evals/**"
---

# Harness evolution: build rules

Distilled from `research/notes/` (evolution_methods, eval_rigor, cross_model,
repair_and_learned_editors, human_in_loop). Paper names below point to the
note with the numbers; read the note before changing a rule.

The loop: the agent runs customer tasks under harness version *v* → failures
are consolidated into a proposal → automated gates screen it → the FDE
accepts, edits, or rejects it → accepted versions go live → survival is
tracked. The research's headline results: **about half of proposed changes
are harmful, and the proposer predicts which ones at roughly chance level**
(priority-ranking paper), and **most evolution gains sit inside eval noise**
(HarnessDev ±4.75 pts, Evo-Bench 2.2 pts between identical harnesses). Every
rule below exists because of those two results.

## 1. Kernel vs surface (enforced in code, not prompts)

- **Kernel (agent can never write):** the eval runner, splits, gates, the FDE
  approval path, logging, the rollback mechanism, and step/cost limits.
- **Surface (agent may propose changes to):** context/prompt blocks, skills,
  tool definitions, retrieval config, control hooks.
- The proposer writes only proposal documents. It never writes `harness_versions`
  directly and never changes the live pointer. Promotion is a kernel function
  called by the FDE action. Prompt-level rules get violated (VeRO: 10 violations
  in one unrestricted run), so enforce this with separate code paths and DB
  credentials.

## 2. Data model: append-only log, derived views

- `harness_versions`: immutable, content-hashed snapshot per version with
  `parent_id` and a typed edge (`extends | repairs | explores | reverts |
  recombines`). Identical content means an identical hash, so no-op proposals
  are detectable.
- `proposals`, `eval_runs`, `traces`, `fde_decisions`: append-only. Nothing is
  updated in place except the derived views below.
- **Derived and recomputable:** the live pointer per (customer, runtime_model),
  the best-validated pointer, evidence validity weights, and survival counters.
- Store **raw traces**, queryable by version, case, and failure category.
  Raw traces beat summaries (Meta-Harness: 50.0 vs 34.9 median). Give the
  proposer query tools (`show_traces(v, failed_only)`, `diff(v_i, v_j)`)
  rather than a pre-packed summary.
- Key every eval result by `(runtime_model, harness_version)`. A version
  accepted on model A is `unvalidated` on model B (cross_model note).
- Proposer recall of past proposals and FDE decisions is **same-customer
  only**. Cross-customer synthesis is a separate downstream step that proposes
  to the base harness. Base and customer harnesses never evolve at the same
  time.

## 3. Proposal record

One document per proposal. Required fields:

`parent_version`, `component_ids` (one preferred), `component_class`
(structural | guidance), `failure_signature` (category + evidence trace ids,
consolidated from **several** failures, not one), `hypothesis`,
`falsification_criterion` ("this fails if …"), `predicted_fixes[]`,
`risk_cases[]`, `diff`, `portability` (invariant | realization |
model-calibrated param).

- **One falsifiable hypothesis per proposal.** Bundled edits cannot be
  attributed; Meta-Harness regressed twice before isolating a confound.
- Prefer **additive** changes and **code-enforced** behavior over advisory
  prompt text. If a rule can be a validator or hook, it must not be prose.
  Code-enforced invariants also transfer across models; prose doesn't.

## 4. Gates before the FDE sees anything

Run in order. A failure is logged to the proposal as `rejected_by_gate` with the
reason and is never shown as a recommendation. FDE attention is the scarcest
resource.

1. **Validity:** it parses, imports, and passes a smoke run on 2–3 cases.
   Infra failures are retried, not blamed on the harness.
2. **Lint:**
   - Block hard-coded eval case IDs, expected answers, or customer-case
     literals (memorization, not strategy).
   - Block references to tools that don't exist.
   - Block executor-specific constants written as literals; they must be
     per-model parameters.
   - **Auto-block** any removal or loosening of step, cost, or safety limits.
3. **Activation:** each change declares when it should fire and emits a
   beacon when it does. Zero fires on the eval means the change is inert:
   reject it (DemoEvolve: a "winning" diff that never fired).
4. **Significance:** paired per-case delta vs the incumbent on the selection
   split. It must exceed the measured noise band (section 5); otherwise label
   it `unresolved`, never "improved".
5. **Replay:** re-run previously passing cases and report **fix and forget
   counts**, not just net. Any forget must be shown to the FDE.

## 5. Eval discipline

- **Splits, frozen with IDs recorded on each version:** `diagnostic` (the
  proposer sees traces), `selection` (the proposer sees only the aggregate),
  `holdout` (the proposer never sees it; it produces the FDE-facing score),
  and `replay`.
- **Noise band:** re-run the unchanged live version K≥3 times, take the median
  re-score discrepancy, and store it on the version. Re-measure after a model
  change.
- **Counterfactual:** would retrying with the current harness (best-of-K at
  matched budget) have fixed it? If yes, it isn't a harness improvement.
- **Proposer confidence is never a promotion signal.**
- The triage (runtime) agent sees only its own case. No planted signal may be
  solvable from a single case, and a strong-model calibration check (strong
  model + base harness) verifies this.
- The system auto-tracks the best-validated version. Don't assume latest =
  best (Evo-Bench: 2 of 3 evolvers froze a worse revision).

## 6. FDE decision and learning signal

- Decisions are **graded**: `accept | edit | reject`, plus a rationale. For
  `edit`, store the FDE's final diff and the normalized edit distance to the
  proposal (0 = accepted as-is, ~1 = rewritten). Binary accept/reject is noisy:
  37% of rejects in one study were style preference.
- FDE-edited diffs are the richest signal. Retrieve them as **positive
  demonstrations** for similar future failure signatures (DemoEvolve,
  HarnessFix repair memory).
- Rejections become "avoid" evidence on that component. Its weight decays as
  the component changes, so an idea rejected against an old version can be
  retested later (DREvo).

## 7. Survival and rollback

- Survival counts only resolved-better, non-no-op accepted changes. Measure it
  at several horizons: still live after N later versions, and not reverted or
  edited.
- Rollback is a single pointer change to any earlier content hash, and a test
  exercises it.
- Regressions are blocked **before** rollout by the backtest gate: a replay of
  all previously seen cases plus holdout, vs the noise band. After rollout, a
  change leaves only through a supersede or retire proposal (backtested the
  same way) or an FDE revert. There is no automatic rollback, and only FDE
  actions move the live pointer.
- A reverted change is negative evidence against both the change and the
  proposer pattern that produced it.

## 8. Memory hygiene (procedural memory)

- Every rule or skill carries an **applicability criterion** ("applies when …
  / not when …").
- A contradicting rule marks the old one `superseded` with a `superseded_by`
  pointer (ARIA). Never keep both active.
- Prune by utility: a memory recalled at least 5 times with average utility
  below 0.5 is retired (ReMe α=5, β=0.5).

## 9. Run state

- Every agent run checkpoints (LangGraph checkpointer) so it can resume. Among
  18 harnesses studied, only one checkpointed (HarnessDev). Don't be the other
  17.
- Scratch reasoning from a rejected proposal is marked invalidated, so the
  proposer doesn't treat it as current state.

## Hackathon cut

Build first, in this order: version store with content hashes and rollback →
proposal schema → lint and activation gates → replay eval with a noise band →
FDE review UI (diff, hypothesis, gate results, fix/forget, accept/edit/reject)
→ survival counter. Everything else (cross-model re-validation, evidence
recalibration, utility pruning, learned proposer) is roadmap: design the
schema so it fits, then don't build it today.
