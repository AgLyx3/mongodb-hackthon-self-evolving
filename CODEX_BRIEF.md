# Codex brief: author the held-out eval customer

You are the **eval author**. A separate builder agent wrote the self-evolving harness in this repo. It must **not** see what you write, so the held-out result is honest. You write the data and the answer key; the builder's frozen loop gets scored against it.

## Deliverables

1. **`services/harness/src/harness/datagen/heldout/heldout_<name>.py`**, one new customer module. Pick `<name>` (lowercase letters/digits), e.g. `heldout_gamble`.
2. **`services/harness/src/harness/datagen/heldout/__init__.py`**, one docstring line. The builder cannot write in this folder.
3. **`services/harness/tests/heldout/test_heldout_<name>.py`**, the audits below as pytest tests.
4. Commit on branch `eval/heldout-<name>` and report the commit hash **and** `git hash-object` of the module file. Don't merge; the user does that.

Put nothing anywhere else. In particular, don't edit `bank.py`, `fintech.py`, `audit.py`, `core/`, `evolution/`, or `spec.py`.

## Interface (must match exactly)

Read `services/harness/src/harness/datagen/spec.py` for the models, and `datagen/bank.py` as a worked example of the shape. **Don't copy its signals.** Your module must expose:

```python
def build(seed: int = <any>) -> Customer          # harness.datagen.spec.Customer
def classify(record: dict) -> tuple[str, str]      # ground truth: (case_type, disposition)
def naive_base(record: dict) -> str                # what the BASE harness gives if read literally
def presentation_rubric(proposal: dict) -> tuple[bool, str, str]   # optional, see §Rubric
```

- **Dispositions:** `close_false_positive | request_info | escalate`.
- **Base harness:** read `services/harness/src/harness/core/base_harness.py`. Your `naive_base` must apply exactly that policy (KYC incomplete → request_info; ≥ $10,000 → escalate; high-risk jurisdiction → escalate; structuring alert → escalate; else close), mapped onto your record fields.
- **Customer id:** `Customer.customer` must equal the module name (`heldout_<name>`).
- **Splits:** `Case.split` values must be exactly: `history` (any size), `batch1`, `batch2`, `batch3` (30 each), `holdout` (40), `report` (40).
- **`Signal` fields:** `signal_id`, `customer`, `shared`, `kind` (`rule|definition`), `description`, `condition` (rules), `disposition` (rules), `field` + `meaning_keywords` (definitions), `locations` (source ids), `signal_type`, and **`family`**.
- **Record schema:** every field a rule condition uses must appear in `record_schema` (dotted path → description). The descriptions must **not** reveal any signal.

## Content requirements

- **Workflow:** compliance alert triage, same as the other customers. Industry: **online gambling operator** (suggested). Synthetic and fictional; say so in `display_name`.
- **Sources (`manifest`):** a different mix from both existing customers. At least one decoy source. At least one `described_as` that is wrong (e.g. a doc claimed current but stale).
- **Signals:** 5–6 planted signals.
  - **Types:** use signal types not used by bank or fintech (e.g. timing between events, a per-player vs per-account aggregation trap, a responsible-gambling flag convention).
  - **Shared signal:** include **exactly one** signal with `signal_id="shared.dormant_reactivation"`, `shared=True`: a dormant account/wallet/player moving a meaningful amount is escalated. Word it and set thresholds your own way.
  - **Families:** plant **two task families**, each with **two sibling signals**. Siblings share `family`, differ in surface details (field, threshold, wording), and should only occur in different rounds: sibling A's cases in `batch1`/`batch2`, sibling B's cases first appearing in `batch3` (plus holdout/report). Leave all other signals with `family=None`. These are the controls.
  - **Evidence:** every signal must be discoverable from ≥ 1 non-record source (interview, chat, QC, doc) and/or record statistics, placed in `chunks` with the matching `source_id`. It must **never** be inferable from a single case.
  - **Oracle:** answers for 3–5 field/code keywords. Unknown questions get no answer.
- **Labels:** from QC review or from outcomes (your choice). If there's no QC sheet, `history_labels` are treated as observed outcomes.

## Difficulty requirements (the existing customers saturate; yours must not)

On the builder's customers, once the harness holds the right rules, a mid-tier and a strong model both score 100%. Labels were pure field lookups, and over-broad rules cost nothing. Design yours so that correct rules alone don't reach 100%, and so that model capability and rule precision both matter:

- **No random noise.** Every inconsistency must have a cause the agent could, in principle, discover. Where history labels disagree with `classify()` (5–10% of history), it must be because of something real, e.g.:
  - a reviewer (with a reviewer id on the row) who applied the old threshold until a dated memo;
  - a team that used a different definition of an outcome;
  - a batch of cases reviewed during an incident.

  Keep `batch*`/`holdout`/`report` labels clean (those are ground truth).

## Realism requirements: mimic real FDE discovery mess

Read `research/notes/fde_mess.md` (if present; it's being written now) and `research/notes/simulated_personas.md`. Encode at least these, deterministically:
- **Not written down:** ≥ 1 signal that appears in no document. It is known only to the customer contact (answered only when asked about the specific field or situation), or visible only as a pattern across free-text case notes.
- **Back-and-forth:**
  - ≥ 1 decision that is made, then reversed. Use chunks dated in order, with the reversal only available from a later round via `meta["available_from_round"]`.
  - ≥ 1 customer-contact answer that is confidently wrong in round 1 and corrected later. Use the oracle list form `[{"from_round": 0, "answer": wrong}, {"from_round": 2, "answer": right}]`, with the corrected answer matching the records.
- **Stakeholders disagree:** an interview and a doc (or two interviewees) disagree. The records settle it.
- **Stale sources:** a manifest `described_as` that oversells a source ("current SOP") which is actually superseded.
- **Scoring still has to be possible:** each such mechanism resolves to one final correct rule or definition in the answer key by round 3. Superseded rules must not be in the answer key; the answer key holds only the final truth.
- **Free-text decisive cases:** for 10–15% of eval cases, the deciding information is only in a free-text field (e.g. `alert.memo`, `player.support_note`) written in natural language with paraphrase. No structured field carries it. At least one planted signal must be of this kind.
  - Encode it as `kind="definition"`, with `field` = the free-text field path (listed in `record_schema`), `meaning_keywords` = 2–4 lowercase words a correct explanation would contain, and `description` = the correct reading.
  - `classify()` still decides these cases, from your own hidden generation variables.
- **Interacting rules:** at least one exception to an exception (rule A overrides the base; rule B overrides A in a sub-case), and precedence must matter on ≥ 3 holdout and ≥ 3 report cases.
- **Over-breadth must hurt:** for every rule signal, include near-miss cases (just outside its scope) whose correct label differs from the signal's disposition *and* from what a plausible over-broad version would give. Target ≥ 2 near-miss cases per signal in holdout and in report.
- **Near-threshold cases:** values at, just above and just below each numeric threshold.
- **Distractor fields:** at least 6 plausible fields that never matter, including one strongly correlated with a signal in `history` only (a spurious correlate).
- **Audit 10 (add to your tests):**
  - a hand-written "over-broad" variant of each rule signal (drop one clause) must change the correct label on ≥ 2 holdout cases;
  - the free-text-only cases must have no structured field that alone predicts their label (check with a one-field decision stump over the history split).

## Audits (write these as tests; all must pass)

1. `build()` is deterministic, including chunks and `history_labels`.
2. Split sizes are exactly as above.
3. For every case, `classify(record) == (case.case_type, case.label)`. Also check a hand-written table of ≥ 8 records against expected outputs, independent of the generator.
4. **Every signal flips the base harness:** for each planted-signal case in batch/holdout/report splits, `naive_base(record) != label`.
5. Each signal decides ≥ 3 holdout cases **and** ≥ 3 report cases.
6. Every rule's `condition` holds on all cases of its type.
7. Each signal's evidence text is really present: assert a distinctive substring in a chunk at each non-record location.
8. **Families:** sibling B's cases never appear in `batch1`/`batch2`.
9. **Difference audit:** run `harness.datagen.audit.difference_audit(harness.datagen.bank.build(), your_customer)` and the same against `fintech.build()`. Both must return `[]`.

## Rubric (optional, presentation feedback)

`presentation_rubric(proposal)` receives `{"hypothesis": str, "falsification_criterion": str, "evidence_refs": [str], "unit_text": str}` and returns `(ok, reason_tag, note)`. It must be **deterministic** (no LLM) and judge **form only, never domain facts**. For example:
- a plain-language statement of what happens;
- n/N counts present;
- at least one quoted snippet;
- falsification is concrete.

Use reason tags such as `too_conclusive` or `not_descriptive`.

## Rules for you

- **No network or LLM calls.** Text comes from templates.
- **Don't run the evolution loop** or anything that calls OpenRouter or Atlas. `pytest` only.
- **Verify:** `cd services/harness && uv run pytest -q tests/heldout` passes, and the full `uv run pytest -q` still passes.
