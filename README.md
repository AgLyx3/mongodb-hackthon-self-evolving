# Self-evolving FDE harness

An agent harness that **learns each customer's deployment the way a forward-deployed engineer (FDE) does**, and only changes itself through an FDE-approved, backtested, versioned loop. MongoDB Atlas holds the memory: versions, traces, evidence, decisions, and vector-searchable history.

> Built for the MongoDB NYC hackathon "Harness Engineering & Model Wrangling", 2026-09-26. All customers, records, interviews and rules are **synthetic and fictional**.

## The problem

When an FDE deploys an AI agent at a new customer, the hard part isn't the agent loop. It's working out which of the customer's sources hold something useful and where inside them it is:
- records with cryptic fields;
- QC sheets;
- stale SOPs;
- interviews;
- Slack threads.

The knowledge then has to go into the agent without breaking what already works. Research on self-evolving harnesses shows why this has to be done carefully:
- **Most automated harness changes are noise.** HarnessDev: evolution gains mostly within a ±4.75-point band.
- **About half of changes are harmful**, and optimizers predict which ones at chance level.
- **Evolved harnesses don't transfer across runtime models.**

See [`RESEARCH.md`](RESEARCH.md) for the literature notes.

## What it does

For each customer, per batch of alerts (compliance alert triage: `close_false_positive | request_info | escalate`):

1. **Triage.** A mid-tier model triages alerts using only the FDE-approved harness. The harness is structured units rendered into an `AGENTS.md`-style prompt.
2. **Reveal.** Outcomes for the batch come back from QC review or observed outcomes.
3. **Investigate.** The investigator probes the customer's sources under a budget. Every probe is logged against a source. Its tools:
   - quantitative label breakdowns over records;
   - **Atlas Vector Search** (automated Voyage embeddings) over interviews, QC comments, docs and chat;
   - costed questions to the customer's contact.
4. **Propose.** The proposer turns findings into **single-unit** changes (a scoped rule or a field definition). It recalls this customer's past proposals and FDE decisions by vector search. It writes with a DB user that can only insert proposals.
5. **Gate.** Validity and lint checks run first, then a **backtest**: a replay of all revealed cases plus a gate holdout. The change must also fire where it applies (kernel-computed), beat the noise band, and cause no regressions beyond noise.
6. **FDE decision.** A **simulated FDE** decides accept, edit (e.g. narrow a too-broad rule) or reject. It is a deterministic checker with an answer key. It only reacts to proposals and never adds knowledge. Edited units are backtested again.
7. **Promote.** Promotion creates an immutable, content-hashed version, and the live pointer moves. Only FDE actions move it.
8. **Learn where to look.** Sources behind surviving changes gain usefulness, which steers the next investigation.

## Results

_Filled in from the final runs below._

## How we kept it honest

- **Planted signals can't be read off a single case.** A strong model (Claude Sonnet 5) with the base harness scores **0%** on them for both customers (calibration).
- **The fintech customer is held out.** The code was frozen (`git tag freeze-before-fintech`) before it ever ran. It differs from the bank in:
  - source mix (no QC sheet);
  - signal types (cryptic codes, a mid-stream policy change in Slack, statistical thresholds);
  - vocabulary.
- **All reported accuracy is on a separate report split** that no gate or decision ever sees. The gates select on a different holdout.
- **Holdout labels, holdout scores and the answer key live in a separate database** (`fde_eval`) that the proposer's DB user cannot read.
- **Adversarial review.** An `evolution-safety` review and a mutation audit of the tests were run, and their findings fixed (commit `b53d176`).

## Architecture

```
services/harness (Python 3.12, FastAPI)
  core/        units, versions, kernel (promotion), simulated FDE — pure, tested
  evolution/   investigator (tool loop), proposer, gates/backtest, batch loop
  adapters/    MongoDB (async PyMongo), OpenRouter (httpx), triage runtime
  datagen/     synthetic customers + answer keys + audits
apps/web (Next.js)  FDE console: proposals, gates, recall, versions, source heat map
```

| Atlas collection | Memory type |
|---|---|
| `units`, `harness_versions`, `live_pointers`, `pointer_events` | procedural (versioned harness) |
| `traces`, `probes`, `findings`, `proposals`, `gate_results`, `fde_decisions` | episodic (append-only) |
| `evidence` (autoEmbed vector index), `proposals` (autoEmbed) | semantic recall |
| `fde_eval.*` | answer key, labels, private scores (app user only) |

## Run it

```bash
cd services/harness
uv sync
uv run pytest -q                          # kernel, gates, FDE, datagen tests
uv run python -m harness.datagen.load     # generate + load both customers
uv run python scripts/calibrate.py        # strong vs mid on the base harness
uv run python -m harness.evolution.loop bank
uv run python scripts/final_compare.py bank
uv run uvicorn harness.api.app:app --port 8000
cd ../../apps/web && pnpm install && pnpm dev   # http://localhost:3000
```

`.env` (not committed) needs `MONGODB_URI_APP`, `MONGODB_URI_PROPOSER`, `OPENROUTER_API_KEY`.

## Not built today

- **Model-switch re-validation:** the pointer is already keyed by `(customer, runtime model)`.
- **Cross-customer synthesis** into the base harness: the planted shared signal is the answer key for it.
- **A learned proposer.**
