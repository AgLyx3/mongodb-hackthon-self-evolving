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
