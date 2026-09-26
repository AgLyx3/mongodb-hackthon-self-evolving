# Handoff: demo shape, eval changes, eval separation

From a review session with the user, 2026-09-26 ~13:45 EDT. For the main
builder agent. Items marked **[approved]** were agreed by the user; items
marked **[pending]** need the user's sign-off before you act on them. Fold the
approved items into `TASKS.md` and keep working; don't redo work already done.

## 1. Framing change [approved]

- **The unit is the customer, not the FDE.** Memory, versions, eval, noise
  band and priors are all per customer (the code already does this). The FDE
  is an actor who signs decisions, not a scope.
- **Scope is the initial discovery path**, meaning onboarding a new customer.
  It is not months of operation afterwards. Don't simulate or claim
  long-horizon use.
  - Label batches as **"discovery round 1 / 2 / 3"** or **"alerts reviewed:
    30 / 60 / 90"**. No week labels.
- **Measure time in alerts processed and probes, not wall-clock minutes.**
  Latency is noisy and cached calls make timing meaningless.
- **"Without" = static base harness on the same cheap model.** The
  matched-budget retry stays optional (cut it if behind, as `TASKS.md` already
  allows).
- **Cross-customer knowledge moves only at checkpoints.** Synthesis proposes
  base-playbook changes (`base v1` → `base v2`); new customers start from the
  latest base. **Future work only; not built today.**

## 2. The demo: three screens [approved]

**Screen 1, "With vs without" (bank).** Same customer, same alert stream;
only the harness differs.
- **Playbook panel:** left side never changes. Right side adds units per
  round, each tagged with its FDE decision (accepted / narrowed / rejected +
  reason). Click → evidence, gate results, fixed/broken cases, what was
  recalled. Show at least one rejection.
- **Chart:** holdout accuracy vs alerts reviewed, noise band shaded.
  - WITH (evolved harness, cheap model) and WITHOUT (static base, cheap model).
  - Dashed line: strong model + base harness, labelled with its cost.
- **Time-to-tap-in table:** probes per signal found and $ spent on decoy
  sources for round 1, round 3 without priors, and round 3 with priors (the
  existing ablation at `evolution/loop.py:126`). Also FDE edits/rejects per
  round.
- **"Corrected once → not needed again" row:** the feedback-uptake result
  (§3).

**Screen 2, "Dev customer vs held-out customer".** Bank and fintech side by
side, same frozen code (`freeze-before-fintech`). Each column shows:
- its growing playbook;
- its accuracy curve against its own noise band;
- its source-usefulness heat map. The heat maps should differ (QC comments
  vs cryptic field + Slack), which is the proof nothing was hard-coded.

The claim is **"the same frozen loop builds a correct playbook for a customer
it has never seen"**, not "bank knowledge helped fintech". Report fintech
honestly even if weaker. State on screen who authored each customer's eval
(§4).

**Screen 3, "Future direction".**
- **Upstream synthesis at checkpoints. One real slice:** after both loops run,
  query the surviving units from bank and fintech and highlight the one that
  matches the planted shared signal ("found independently in two customers →
  candidate for base v2"). The proposing and gating of base changes stays
  labelled as future work.
- **Roadmap list:**
  - model-switch re-validation (backtest each customer's playbook when the
    runtime model changes; flag rules that stop helping);
  - third customer (gambling operator);
  - noisy-FDE setting.

## 3. Feedback uptake: new eval [approved in principle; build order below]

**Question:** after the FDE corrects the harness once, does it avoid needing
the same correction on a *similar* case later?

- **Two feedback kinds. Keep them apart.**
  - **Content** (rule too broad, wrong disposition) → customer playbook units
    (kernel path, exists).
  - **Presentation** (e.g. "right source, but too conclusive; not descriptive
    enough for a person to follow") → proposer/investigator memory only,
    recalled via the existing same-customer `$vectorSearch` in
    `evolution/proposer.py:59`. Never rendered into the triage runtime.
- **Task families with hidden labels.** Each planted signal gets a `family`
  tag in the answer key. Plant **two siblings per family in different rounds**
  (early + later, different surface details). The agent never sees family tags.
- **Metric:** on the later sibling, first-pass FDE acceptance and edit
  distance, **memory on vs recall off** (same batch, same budget; mirror the
  priors ablation).
- **Control:** later signals from families with no earlier sibling. They
  should not move with memory. Improvement = drift; degradation =
  over-generalization. Report either.
- **Simulated FDE presentation rubric: deterministic, not an LLM judge.**
  Checks along the lines of: plain-language statement of what's happening,
  n/N counts, a quote, affected cases listed. Failing → reject with a reason
  tag such as `too_conclusive`. Critiques form only, adds no domain knowledge
  (decision 4).
- **Small n.** Show per-case evidence (round-1 correction → round-3 first-pass
  accept, with the recalled decision linking them) and state n. No
  statistical claim.
- **Build order:**
  1. content families (mostly a data change);
  2. presentation rubric, only after the bank loop runs end to end (17:30
     checkpoint);
  3. cut the whole section if 17:30 slips.
- **Naming.** Call it **feedback uptake** (or lesson survival), not plain
  "survival". "Survival" keeps its meaning: an accepted change stays live, holds
  on evidence the proposer never saw, and breaks no backtest cases. **[pending]**
  `CLAUDE.md` wording for both. It's a dev-rule change, so propose it to the
  user; don't edit it.

## 4. Eval separation: the builder must not author the eval [approved]

The agent that builds the loop must not write the evals it is scored on.

| Separation | Status |
|---|---|
| Proposer (runtime) ↔ eval data | Enforced: `eval_db` + `fde_proposer` DB user |
| **Builder ↔ eval author** | **Gap.** Builder wrote `datagen/bank.py`, `datagen/fintech.py`, `core/fde.py` |
| Eval runner | Fine: deterministic code |

What to do:
1. **A different agent authors the eval pieces.** The user will run Codex
   with a bounded brief. The pieces:
   - regenerated fintech signals;
   - sibling families + hidden tags (fintech required; bank optional);
   - the presentation rubric.

   Do not write these yourself.
2. **You get the interface, not the contents.** Agree an answer-key *schema*
   (e.g. `signal_id`, `family`, `location`, `applies_when`, `affected_case_ids`,
   `shared`) and score against it. Don't read the values.
3. **Stop reading fintech now.** No further reads of `datagen/fintech.py`,
   fintech answer keys, or fintech traces until the freeze. **[pending]** A
   `.claude/settings.json` read-deny for the eval-author paths + a guard on
   direct `eval_db` queries. Propose the diff to the user; don't apply it.
4. **Commit and hash the eval before any loop runs on it.** Put the hash in
   the README.
5. **Honest labelling.** Bank = dev customer, builder-authored. Fintech =
   held-out, authored by a separate agent and hidden from the builder. Say so
   in the README and on screen 2.

## 5. Code gaps found in review

1. **`fde_id` missing on `FdeDecision`** (`core/kernel.py:43`). Make it
   required and give the simulated FDE a persona name. Every screen shows who
   approved what (glass box). **Fix.**
2. **Base playbook isn't versioned.** `base_units()` is code, and each
   customer's first version has no parent. Label it `base v1` in the UI for
   screen 3. **Don't build base versioning today.**
3. **`httpx` is imported directly** (`adapters/llm/openrouter.py`) but not
   declared in `pyproject.toml`; it only arrives transitively. Adding it is a
   dependency change: **ask the user.**
4. **Commit cadence.** The `CLAUDE.md` Git rule now says: commit on a
   non-`main` branch each time a `TASKS.md` item is done and its tests pass;
   never commit secrets, `.env`, or generated data. Commit current work and
   bring `TASKS.md` up to date (it still says DRAFT with nothing ticked).
   Before the first commit, confirm `secrets/` is gitignored.

## 6. Pending user decisions (don't act until approved)

- `CLAUDE.md` wording for survival vs feedback uptake.
- `.claude/settings.json` read-deny for eval-author paths.
- Adding `httpx` as a declared dependency.
- The Codex brief for the eval pieces (user runs it).
