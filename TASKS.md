# TASKS.md: Day-1 build plan (DRAFT, awaiting approval)

**Goal:** a working loop for compliance alert triage across two customers: bank (dev) and fintech (held-out). Show it improves beyond noise and learns where to look. Submissions are due **22:00 EDT**. Design: `RESEARCH.md` §5.9 (decisions 1–11). Solo; $10 OpenRouter (hard stop at $9).

Layout: `services/harness/` (Python 3.12, uv, FastAPI) + `apps/web/` (Next.js, pnpm), matching the `.claude/rules` path globs.

## Blocked on user
- [ ] Create `.env` from `.env.example` (Atlas URIs for `fde_app` / `fde_proposer`, `OPENROUTER_API_KEY`)
- [ ] Approve dependencies (listed under Phase 0)
- [ ] Approve installing `pnpm` (not on this machine), or use npm for the web app instead

## Checkpoints (cut scope if missed)
| Time | Must be true | If behind |
|---|---|---|
| 15:00 | Bank data in Atlas; kernel tests pass; calibration check done | Shrink to 3 signals per customer |
| 17:30 | Bank loop runs 3 batches end to end, with metrics | Drop the matched-budget retry baseline; keep static + strong |
| 19:30 | UI shows versions, proposal review, heat map, metrics | Ship a single-page UI; no polish |
| 20:45 | Freeze tag; fintech run finished | Report partial fintech results honestly |
| 21:30 | Submission check, demo recorded | No new features after this |

## Phase 0: Scaffold (≈30 min)
- [ ] `git` branch `build/day1` (done); first commit of docs and config
- [ ] `services/harness`: uv project. **Deps to approve:**
  - `deepagents==0.7.19` (pinned)
  - `langgraph`, `langgraph-checkpoint-mongodb`, `langgraph-store-mongodb`
  - `langchain-openrouter` (fallback `langchain-openai` pointed at OpenRouter)
  - `pymongo`, `fastapi`, `uvicorn`, `pydantic`, `pytest`
  - `voyageai` (only if Automated Embedding is unavailable)
- [ ] `apps/web`: Next.js App Router + TS. **Deps:** `next`, `react`, `typescript`, Tailwind, shadcn/ui, a chart lib (Recharts)
- [ ] Fill in the `CLAUDE.md` Commands table (proposed diff for the user; I won't edit it directly)
- [ ] Connectivity smoke test with both DB users; verify `fde_proposer` **cannot** write outside `proposals` (test)
- [ ] Check Automated Embedding availability; pick the embedding path; record model + dimensions

## Phase 1: Data generator (≈1h30)
- [ ] Customer config schema: sources, conventions, disposition rates, label source, vocabulary, planted signals, decoys
- [ ] `bank.yaml` and `fintech.yaml` per the §5.9 difference matrix. 4–5 signals each plus 1 shared.
- [ ] Records generated **in code** (seeded). About 150 alerts per customer with linked records. Splits: 3 batches × ~30, holdout ~40, replay pool.
- [ ] Qualitative text (QC comments, SOP, Slack, interviews) from **templates plus a cheap LLM** built from the answer key. A checker confirms each signal is present and nothing extra is. Cached. Budget ≤ $0.75.
- [ ] Answer key: signal → location, meaning, correct scoped rule (`applies_when`), affected cases (each ≈10–15% of holdout), specific vs shared
- [ ] Customer-contact oracle: answers from the answer key; unknown → "don't know"
- [ ] **Rules checks (tests):** no signal can be solved from a single case (decision 9); difference audit (decision 11)
- [ ] Load into Atlas: `customers`, `source_manifests`, `records_*`, `evidence` (chunks + vector index), `cases`

## Phase 2: Kernel: unit store, versions, promotion (≈1h15), tests required
- [ ] Collections: `units`, `harness_versions` (set of unit hashes, `parent_id`, typed edge), `live_pointers` (customer, runtime_model), `proposals`, `gate_results`, `eval_runs`, `traces`, `probes`, `fde_decisions` (append-only)
- [ ] Content hashing; no-op detection; `promote(proposal, fde_decision)` is the only path that moves a pointer; rollback = pointer move
- [ ] Tests: immutability, no-op detection, promotion needs an FDE decision, rollback, proposer DB user cannot promote
- [ ] Run `evolution-safety` subagent review on the kernel diff

## Phase 3: Runtime triage + calibration (≈1h)
- [ ] Render units → Deep Agents files (`AGENTS.md`, `skills/*/SKILL.md`); built-in file/shell/subagent tools off; harness is read-only
- [ ] Case-scoped tools (only this alert's records); structured output = disposition + cited records
- [ ] Beacons: each unit that fires or loads is logged to the trace
- [ ] LLM wrapper: OpenRouter, cache keyed by input hash, spend counter with hard stop at `LLM_SPEND_LIMIT_USD`
- [ ] Pick model IDs from the live OpenRouter list: one mid-tier, one strong
- [ ] **Calibration check (decision 8):** mid-tier and strong, each with the base harness, on bank holdout. If strong solves the planted-signal cases, **redesign the data before continuing**. Budget ≤ $1.

## Phase 4: Investigator + proposer (≈1h30)
- [ ] Source profiles (cheap: schema/field stats, QC dimensions, topic summaries), embedded
- [ ] Investigator: start from failures; run contrast aggregations over records, vector search over qualitative evidence, oracle questions (costed); every probe logged; budget per batch
- [ ] Findings with evidence links (stance; n/N or quote)
- [ ] Proposer (`fde_proposer` credentials): one unit change per proposal; required fields per the rules §3 + `applies_when`; recalls **same-customer** past proposals/decisions via vector search; ≤ 3 per batch
- [ ] Investigator source priors = derived view from survival (decision 3)

## Phase 5: Gates + backtest (≈1h)
- [ ] Validity → lint (hard-coded cases/answers, loosened limits) → activation (beacon fired) → significance vs noise band → **backtest** (replay of all seen cases + holdout; fixed/broken IDs)
- [ ] Noise band: K=3 runs of the unchanged version per customer
- [ ] Tests for each gate that prove it can fail (`check-auditor`)

## Phase 6: Simulated FDE (≈30 min)
- [ ] Reactive checker (decision 4): accept / narrow `applies_when` / reject from the answer key; reason tags; templated persona rationale; edit diff + normalized edit distance

## Phase 7: Batch loop, baselines, metrics (≈45 min)
- [ ] Loop over 3 batches for the bank; fates: supersede / retire / revert
- [ ] Baselines: static base (mid), strong + base, matched-budget retry (drop if behind)
- [ ] Metrics: holdout accuracy per version vs noise band; findings recall/precision; probes to find each signal and budget on decoys; batch-3 **with vs without** learned priors; FDE edit distance and reject rate; survival

## Phase 8: FDE review UI (≈1h30)
- [ ] Version timeline per customer (units added/retired, typed edges)
- [ ] Proposal card: evidence + provenance, diff, hypothesis, `applies_when`, gate results, fixed/broken cases, **what was recalled and why**, FDE decision
- [ ] Source usefulness heat map per customer (bank vs fintech side by side)
- [ ] Metrics chart with the noise band shaded
- [ ] "Future goals" panel: model-switch re-validation, cross-customer synthesis
- [ ] `ui-critic` review

## Phase 9: Held-out fintech (≈30 min)
- [ ] Commit, then `git tag freeze-before-fintech`. No code or prompt changes after this.
- [ ] Run the fintech loop; compute the same metrics; report honestly

## Phase 10: Submit (≈30 min)
- [ ] `/submission-check`; README with results and the research framing; demo recording script

## Stretch (only after Phase 10 is safe)
- [ ] Gambling operator customer
- [ ] Cross-customer synthesis pass → base-harness proposals, scored against the shared signal (decision 6)
- [ ] Random-mutation baseline; FDE noise setting

## LLM budget ($10, hard stop at $9)
| Item | Est. |
|---|---|
| Data text generation | ≤ $0.75 |
| Calibration (mid + strong) | ≤ $1.00 |
| Bank loop (3 batches, noise band, backtests, investigator, proposer) | ≈ $2.00 |
| Fintech loop | ≈ $2.00 |
| Final comparison (strong + base) | ≤ $0.75 |
| Buffer | ≈ $2.50 |

## Decisions approved
See `RESEARCH.md` §5.9 decision log (1–11). The dev rule `harness-evolution.md` was updated per user approval (no auto-rollback; same-customer recall; case-only triage + calibration).

## Verification results
(none yet)
