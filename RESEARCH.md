# RESEARCH.md — Self-Evolving FDE Deployment Harness

Living research log. Started 2026-09-26.

**Working thesis** (from `self_evolving_fde_harness_research_report.docx`): treat each customer deployment as a versioned, continuously evolving agent harness. New evidence → agent-proposed mutation → eval → FDE accept/edit/reject → versioned. Two memories: append-only episodic (evidence, proposals, feedback, outcomes) and mutable procedural (current harness: context, skills, tools, control, retrieval, evals). Learning signal = which mutations *survive* expert review and later evidence.

**Open hypothesis (ours):** agents can write good harnesses *for themselves*, but those harnesses don't transfer across models. The harness is co-adapted to its runtime model.

---

## 1. Source proposal — key points

- Unit of capture is the **decision trace**: evidence → finding → proposed change → FDE judgment → accepted state → later evidence → outcome.
- Mutation taxonomy: context/instructions, skills, tools, control logic, retrieval policy, evals.
- Mutation object schema: `mutation_id, parent_version, evidence_refs, hypothesis, component, proposed_diff, scope, pre_review_eval, fde_action, fde_delta, fde_feedback, deployed_version, later_fate, outcomes`.
- "Continuously evolving" = stateful, empirical, reversible, learns from corrections.
- Key metric: **mutation survival**. Accept-then-rollback is the most informative label.
- V0 = within-deployment loop; cross-deployment learning is a later extension.
- Borrowed from: GEPA, ReMe, Letta Context Repositories, Reflexion, Voyager, Darwin Gödel Machine, ExpeL, Promptbreeder.

---

## 2. HarnessDev (arXiv 2609.01437, Sep 2026) — read in full

**Setup.** Six creator LLMs (Opus 4.8, GPT-5.5, Gemini 3.1 Pro, DeepSeek V4 Pro, Qwen 3.7 Max, Seed 2.0 Pro). They start from a weak seed harness that scores 0 (no loop, planner, verifier, state, retry, or stop rule).
- **Creation:** build a harness from a spec plus 1–3 dev cases.
- **Evolution:** improve their own harness from feedback on SWE-Pro-100 + Terminal-Bench-89, with a budget of 10 full evals.
- Scored on held-out tasks (2,207 instances across 5 benchmarks), with the harness frozen before evaluation. Creator and executor model are separated.
  - **Self-Eval:** executor = creator.
  - **Unified-Eval:** executor = Gemini for every harness.

### Findings

| # | Finding | Evidence | Implication for us |
|---|---|---|---|
| H1 | Created harnesses trail human-built ones, except on writing and ML | Best was Opus Self-Eval avg 67.8 vs human 86.2. Matches human on EQ-Bench, beats it on MLE-bench. Biggest gap on search. | Base harness from humans still matters; the agent adapts it rather than building from scratch |
| H2 | **Harnesses co-adapt to their creator model** | Opus SWE-Pro 69.3 → 33.0 under Gemini. Opus hard-coded a 120-step limit. Duplicate-query rate in Opus's search harness went 10.1% → 88.2% under Gemini. | Supports our hypothesis |
| H3 | **…but a model's own harness isn't always best for it** | Qwen/DeepSeek harnesses *improve* under Gemini (Qwen +17.6 BrowseComp, +12.9 MLE). The weak executor was the bottleneck. | The issue is harness–model *compatibility*, not ownership |
| H4 | Evolution gains transfer poorly across runtime models | Self-runtime: all 5 improve on held-out (+1.43 to +4.44, mean +3.11). Fixed-Gemini: 3 of 4 regress (GPT-5.5 −10.32). | Version (harness, runtime model) together; treat a model swap as a non-stationarity event |
| H5 | Most evolution steps are noise | 64 switches: only 2 clearly beyond noise, 27 inside the noise band, 8 regress on both benchmarks. The same commit varies about ±4.75 pts. | Promotion needs repeated runs and noise bands |
| H6 | Visible feedback is a poor guide for choosing the final version | Feedback and held-out move the same way 53.1% of the time. Only 2 of 9 self-declared versions were held-out-optimal. | The agent shouldn't choose its own promoted version. FDE review plus held-out slices supply the selection signal |
| H7 | Lots of dead code | 113 of 169 new functions reachable. State/memory never triggered (0 checkpoints in 26,679 trajectories). 124 of 587 writing features are dead. | Add an "activated in runs" field to the mutation schema |
| H8 | Diagnosis is the weakest step | Trajectory tool called twice. 0.5–40.2% of feedback tasks inspected. Self-test count ρ 0.13–0.26 (n.s.) vs revision calls ρ 0.57. | Pair each mutation with evidence it fixes; verify at case level |
| H9 | Best improvement came from spotting self-report ≠ truth | Opus: 99/100 runs reported success, 48 passed → added a completion gate | Keep scoring separate from the harness's self-report |
| H10 | Cost varies about 19× and doesn't predict score | MLE-bench token use | Track cost per mutation |
| H11 | Edit size doesn't predict gains; deletion can help | Gemini had the fewest lines (1,006) and the best Terminal-Bench score (68.8) | Rollback/removal is a first-class mutation type |

**Positioning.** HarnessDev §2 explicitly frames FDE work as three layers: (1) vague target, (2) absent or unreliable feedback, (3) missing execution system. It studies only (3), with no human in the loop. Our proposal targets (1) and (2), using human FDE judgment as the feedback and selection signal.

---

## 2b. Harness Updating Is Not Harness Benefit (arXiv 2605.30621, May 2026) — read in full

Lin, Wu et al. (Penn State / UCSC / Amazon). The paper splits self-evolution into two capabilities:
- **harness-updating**: the evolver model writing useful updates from execution evidence.
- **harness-benefit**: the task-solving agent actually gaining from updated harnesses.

**Setup.** Seven models: Opus/Sonnet 4.6, Haiku 4.5, Qwen3-235B, Qwen3-32B, GPT-OSS-120B, and Qwen3.5-9B (evolver only). Benchmarks: SWE-bench Verified, MCP-Atlas, SkillsBench. Evolvable components are **text only**: skills, plus prompts and memories on MCP. Tool interfaces and execution policy are *fixed*. Each agent × evolver pair runs a solve → evolve loop, with the evolver reading **that agent's own trajectories**.

| # | Finding | Evidence | Implication |
|---|---|---|---|
| U1 | **Which model writes the update barely matters** | Best-to-worst evolver gap ≤ 3.1 pp on any benchmark, and no evolver wins everywhere. Qwen3.5-9B has the top SkillsBench gain (3.8 pp vs Opus 2.3). On one task, the 9B and Opus skills are "procedurally isomorphic". | Use a cheap evolver; spend budget on the runtime agent |
| U2 | Post-evolution score depends mostly on the runtime agent | Spread across evolvers for one agent ≤ 5.1 pp, vs a 36.0 pp base gap between agents. Even pairing the weakest agent with its best evolver against the strongest agent with its worst evolver, the strong agent leads by 18.6–35.2 pp. | — |
| U3 | Benefit is non-monotonic: mid-tier models gain most | SWE: Qwen3-235B +19.3, GPT-OSS +15.8, Opus +2.6 (ceiling), Qwen3-32B +4.4 | — |
| U4 | **Failure mode 1: activation.** Weak models don't load the harness at all | Skill-load rate: Qwen3-32B 0.251, GPT-OSS 0.446, strong models ≈0.96. Example: a malformed multi-key load call is rejected by the format gate. | Log whether each mutation was *loaded* (same idea as HarnessDev's dead code) |
| U5 | **Failure mode 2: adherence.** Models load the harness but don't follow it | Harness-following rate: Opus 0.757 vs Qwen3-235B 0.350 at the same ≈0.96 load rate. Adherence drift from load to final step: Qwen3-32B 0.52→0.13, GPT-OSS 0.67→0.43, Opus 0.89→0.80. | Rules written for strong models may be silently ignored by weaker or cheaper ones |
| U6 | Ethics: persistent harness updates can store wrong lessons or unsafe rules | Authors call for reversibility, auditability, and human oversight | Supports FDE gating |

### Reconciling with HarnessDev — refines our cross-model hypothesis

The two papers seem to disagree. Here, a harness written by model A works fine for model B. In HarnessDev, a harness evolved on A breaks on B. The difference is *what* evolves and *whose evidence* drives it:

1. **Author ≠ adaptation target.** In this paper, the evolver's model changes but the evidence always comes from the runtime agent. So the harness is still fit to the agent that runs it, and cross-*authoring* works. HarnessDev's failure is cross-*execution*: the harness was fit to A's trajectories and then run by B.
   → **Revised hypothesis:** a harness is co-adapted to the model *whose trajectories it was evolved on*, not the model that wrote it. Any model can be the "FDE-assistant" evolver. What matters is re-validating whenever the runtime model changes.
2. **Portability depends on the layer.** Text skills and procedures ("filter FINISH events", "try this TTS fallback chain") are procedural knowledge and port well. HarnessDev's failures are in *control code*: step limits, dedup and stop rules, message protocols. These match our split between customer truth and model-bound settings.
3. **Portable ≠ usable.** Even a portable skill needs the runtime model to load it (U4) and follow it over long tasks (U5). This matters for FDE deployments where customers downgrade to cheaper models for cost.

---

## 3. Related work

Summaries below; full per-paper notes with exact numbers are in `research/notes/*.md`. Subagents read the full PDFs, and numbers were copied from the text.

### 3.1 Harness repair & learned editors → [`research/notes/repair_and_learned_editors.md`](research/notes/repair_and_learned_editors.md)

| Paper | Mechanism | Key numbers | Borrow |
|---|---|---|---|
| **HarnessFix** (2606.06324) | 4 prompted agents, no training. Traces become a provenance/control-flow representation linked to specific harness files, prompts, and tool schemas. Repeated failures are grouped into flaw records. Repairs come from a fixed set of scoped types (from a study of 30 OSS agent repos). A held-out gate includes a regression budget. | +6.3 to +18.4 pts over the seed (GPT-5-mini). Failing-step localization: 55.0% on raw traces → 85.0% with the structured representation. | Link each mutation's evidence to the exact harness artifact. Scoped repair types = our component taxonomy. Keep a memory of accepted and rejected repairs with reasons. |
| **Harness-R1** (2608.02276) | The only *trained* editor. A 9B "engineer" model gets supervised fine-tuning on 877 filtered teacher patches, then GRPO, with reward = improvement on the same batch. It edits code hooks at 4 points in the agent loop. | Avg 44.3% → 53.6% (supervised-only 46.4%; best frontier prompted editor 48.8%). From 10 failures: +8.9±1.5 on held-out, while large prompted editors go negative. Used about 1,500 failure batches × 8 candidates. | Long-term path for learning a mutation policy. Needs data pooled across deployments. |
| **DemoEvolve** (2605.24539) | Adds human demonstration trajectories when reward is sparse or noisy | The Meta-Harness winning hook fired **0 times in 517 requests** (selected on noise). 9 demonstrations: Balatro completions 6/15 → 12/15. Tiny sample, one domain. | FDE demonstrations and walkthroughs are a strong input. Check that a mutation *fires* before trusting its score. |
| **VeRO** (2602.22480) | Infrastructure: versioned commits, budget-gated eval, access control, per-sample traces | 0.61 with full infrastructure vs 0.53 for the same model without it. Optimizers mostly fall back to prompt edits. Constraints stated only in the prompt → 10 violations (test leakage, budget overrun). | Enforce eval isolation and budgets in code, not in the prompt |

**Takeaways for the mutation policy:**
- **V0, no training:** retrieve past mutations with their accept/edit/reject verdicts and reasons. Show FDE-edited versions to the proposer as few-shot examples.
- **Later:** supervised fine-tuning on accepted and edited patches, then preference learning.
- **Log FDE edits as structured diffs.** One `(proposal, FDE edit)` pair is three signals at once: a preference pair, a positive demonstration, and a repair-type label.
- **Converging evidence on dead mutations.** This is now the third paper, alongside HarnessDev H7 and Updating/Benefit U4, showing that mutations often never execute. An activation check is required before review.

### 3.2 Human-in-the-loop & procedural memory → [`research/notes/human_in_loop.md`](research/notes/human_in_loop.md)

**Novelty check:** no published system found that combines **human expert review of agent-proposed harness mutations + versioned mutations + survival/rollback tracking as a learning signal**. Each piece exists separately. Search wasn't exhaustive → phrase the claim as "to our knowledge". No peer-reviewed work on AI-assisted forward-deployed engineering was found (industry blogs only).

| Work | What it does | Key numbers | Borrow |
|---|---|---|---|
| **PRELUDE / CIPHER** (NeurIPS 2024) | Learns latent user preferences from the user's edits to outputs. Cost = token-level Levenshtein distance. | Email: cumulative edit cost 31,103 (no learning) → 8,391 (CIPHER); oracle 1,851. Simulated user; edits outputs, not prompts. | Use **edit distance between proposed and committed diff** as the graded FDE signal |
| **ARIA** (arXiv 2507.17131, EMNLP 2025 per its page) | Agent asks a human expert questions. Old rules are marked **Superseded** with a pointer to the replacement. | Sensitivity 0.891 vs 0.705 for static GPT-4o at 1,000 questions. Rich feedback beats labels-only (0.833 vs 0.795 at 100 questions). | `superseded_by` links in episodic memory. Collect FDE rationale, not just a label. |
| **Copilot feedback in customer support** (arXiv 2604.23855) | Operator accept/reject on an agent copilot | 45% of sessions automated, −39% handle time. Binary feedback: **37.2% of rejections were operator preference or optional steps**. Authors call for graded feedback. | Directly supports graded accept > small edit > rewrite > reject. Tag *why* something was rejected (wrong vs just a preference). |
| **Airbnb AITL** (EMNLP 2025 Industry) | Agent adoption + rationale feedback | +11.7% recall@75, +8.4% helpfulness. Updates weights, not a versioned harness. | Rationale feedback pays off in production |
| **ReMe** (arXiv 2512.10696, Findings ACL 2026) ✅ docx citation verified | Automated procedural memory: distill → reuse → refine. Prunes a memory once it has been recalled ≥5 times with average utility <0.5. | AppWorld, Qwen3-8B Avg@4: 14.97 → 24.70. ⚠ The docx's implied "8B + ReMe beats memoryless 14B" doesn't hold on every metric (BFCL-V3 Avg@4: 45.17 vs 48.66). | Utility-based pruning. Our survival metric is a **human-grounded version** of this rule. |
| **Letta Context Repositories** ✅ exists, but it's a **blog post** (Feb 12, 2026), not a paper | Git-versioned memory files, background reflection, defragmentation | No benchmarks, no utility pruning, no human approval | Cite as a system/blog, not a paper. Fix in docx. |

Smaller items in the notes: iPrOp, SkillForge, Evidence-in-the-Loop, EvoUndo, StarHarness.

### 3.3 Harness evolution methods → [`research/notes/evolution_methods.md`](research/notes/evolution_methods.md)

| Paper | Core mechanism | Key numbers | Borrow |
|---|---|---|---|
| **Meta-Harness** (2603.28052) | A coding-agent proposer reads *every* prior candidate's code, scores, and raw traces through a filesystem | Raw traces vs summaries: median/best 50.0/56.7 vs 34.9/38.7. +7.7 over ACE. TerminalBench-2: 76.4% (Opus 4.6), 37.6% (Haiku 4.5). | Queryable raw-trace store. Hypothesis-first proposals. Keep prompt edits separate from control-logic edits. Leakage regex check. |
| **HarnessCompass** (2608.01918) | A gate bans task-specific edits. Every rule must declare its **applicability condition**. Structural and guidance components evolve on separate tracks, then merge (R³). | SWE-bench Verified 54→66% in 5 iterations (vs AHE's 63% in 20). Held-out 60.4 vs 54.7. | Change-manifest fields `predicted_fixes` / `risk_tasks`. "Enforce in code, not advice." Mandatory applicability = our `scope` field and the fix for overgeneralization. |
| **DREvo** (2607.26722) | Past outcomes → component-anchored evidence units, **reweighted against the current harness**: consistency × 0.9^age × AST similarity. Actions: Exploit / Avoid / Retest / Explore. | ⚠ No train/test split on agentic tasks (authors admit it). Agentic average gain reported inconsistently (13.8% vs 14.2%). | A validity weight over our append-only log, so **old FDE rejections fade once the component has changed**. This solves "a stale rejection blocks a now-valid idea". |
| **Hierarchical Self-Improvement (HSI)** (2608.08466) | Harness / evolver / meta-evolver, with an **outer layer the agent can't edit**. Proposals include a falsification criterion. History is a typed version graph. | BALROG avg 18.9 → 41.4. **No gain on NLE** (feedback too sparse). | Non-editable anchor = the FDE-owned policy layer. Each mutation states "what would prove this wrong". |
| **HarnessBank** (2607.13683) | Archive keyed by (component × failure pathology). Gated verification: validity → activation → significance (z ≥ 1.96) → gain. | Test +9.3 to +15.4 on 6 domains. SWE-bench (+5.1) not statistically credited. | **Run these 4 gates before the FDE sees a proposal**, so reviewers only see non-noise, actually-firing changes |

**Open design choice:** should the proposer get full raw history (Meta-Harness) or bounded, distilled context (DREvo, HSI)? The subagent's suggestion: distilled context up front, plus on-demand drill-down into raw traces. This fits our two-memory split: procedural state plus retrieved episodes, with raw evidence available through `evidence_refs`.

### 3.4 Evaluating harness evolution → [`research/notes/eval_rigor.md`](research/notes/eval_rigor.md)

| Paper | Key finding | Numbers |
|---|---|---|
| **Rethinking the evaluation of harness evolution** (2607.12227) | **At a matched budget, evolution loses to doing nothing and to plain sampling** | Terminal-Bench 2.1, K=5: evolution 67.4 pass@1 < seed 68.2 < parallel sampling 72.3. Disjoint 45/10/34 train/val/test split: only +0.6. |
| **SEAGym** (2606.17546) | Validation gains don't predict shifted-domain (OOD) gains. Evolution **forgets** earlier-solved tasks. | AHE and TF-GRPO both +17.1 on validation. OOD: AHE +6.3, TF-GRPO −2.5. AHE on replayed training tasks dropped from 43/80 to 6/80 at an intermediate point; final version fixed 13, broke 4. Batch size non-monotonic (only 20 positive). |
| **Evo-Bench** (2608.09096) | A direct noise floor. Evolvers freeze versions worse than their own best. | ±2.2 pts across **byte-identical** harnesses. 2 of 3 evolvers froze worse than their best. Best evolved 46.3 < human 47.5. |
| **HarnessOpt-Bench** (2608.06301) | Treats differences inside a measured "resolution band" as ties. Visibility is tiered: dev = traces, validation = aggregate score only, test = hidden. | Band ±0.035–0.066 normalized gain. Best validation score is usually higher than final test. (Paper gives the eval-call cap as both 100 and 200.) |
| **Priority ranking** (2605.22505) | Humans rate a large share of optimizer steps as harmful. **An optimizer can't tell whether its own update helps.** | 44.8–48.2% of steps judged harmful. 94.4% of non-prompt errors survive to the final harness. Self-prediction accuracy ≈ chance (0.33–0.55). Ranking ability ↔ real gain ρ = 0.602 (p = 0.038). (Paper gives both 108 and 122 flawed harnesses.) |

**Protocol for evaluating mutations** (combined from all five):
1. **Measure a noise band per customer** by re-running the unchanged harness. A delta inside the band = *unresolved*, not accepted.
2. **Hold out a split the proposer never sees.** Only it decides promotion. Tiered visibility: dev traces / validation aggregate / test hidden.
3. **Replay previously passing cases** on every mutation. Record fixed and broken case IDs. This catches forgetting (SEAGym) and regressions (HarnessDev H5).
4. **Baseline against matched-budget resampling of the unchanged harness.** A mutation must beat "just retry".
5. **Screen statically** for hard-coded case details and removed limits/guardrails.
6. **Auto-track the best version and support one-click rollback.** Evolvers routinely freeze worse versions.
7. **Never use proposer confidence as a promotion signal.** Self-prediction is at chance.

**Gap we can fill:** none of the five papers has a matched-budget **random-mutation** baseline. Sample sizes are small throughout (1–2 runs per configuration, validation sets as small as 4 tasks).

### 3.5 Cross-model transfer → [`research/notes/cross_model.md`](research/notes/cross_model.md)

**Verdict:** the co-adaptation hypothesis is mostly supported, with a refinement. The model-tuned layer doesn't transfer. General execution scaffolding does.

| Paper | Finding | Numbers |
|---|---|---|
| **Harness-Bench** (2605.27922) | The harness matters a lot, and matters **more for weaker models**. It does not evolve harnesses, so it doesn't test transfer directly. | 6 harnesses × 8 models, 5,194 runs. Best vs worst harness 76.2 vs 52.4 (23.8 pts); ~27 pts on GPT-5.4 alone. Among failed runs: output-contract violations 36.4%, unrecovered tool errors 24.6%. |
| **Self-Harness** (2606.09498) | Model-specific edits help every model tested. **No cross-model experiment.** Its "held-out" split is also used to accept edits, so it isn't clean. Key pattern: **every model converges on the same goal** (verify patches, page through all records, write required outputs early) **but implements it differently** (prompt guard / subagent / middleware / a limit like "50 tool calls"). | 9 of 9 model–benchmark pairs improved, up to +40.6 pts (+132% relative) |
| **PromptBridge** (2512.01420) | Prompts optimized for one model often give zero gain or large losses on another. **Strong → weak transfer hurts more** than weak → strong. A small calibration set plus a learned rewrite recovers much of it. | GEPA-optimized prompt on Llama: 35.98 on HumanEval vs 68.70 for direct transfer. Calibration built from 5 tasks. |
| **Counter-evidence:** MemoHarness, HarnessCompass | Transfer works when edits are limited to structured, task-agnostic changes | MemoHarness +0.098 mean on 6 other models (only 18 test tasks). HarnessCompass +3.8 on Claude, with some per-repo drops. |

**Portable vs model-bound** (consistent across all sources):
- **Portable:** output-contract validators, verification gates, permissions, state and traces, retrieval content, customer workflow facts, policies, eval cases.
- **Model-bound:** prompt wording, tool-call format, step and token budgets, thresholds, stopping rules.

---

## 3b. Candidate demo benchmarks (web search, 2026-09-26)

| Benchmark | What it is | Released | Fit for a 1-day demo |
|---|---|---|---|
| **τ^τ-bench / hyper-tau-bench** (arXiv 2609.04611, Sierra) | Literally an FDE benchmark. A developer agent gets business records, a simulated client with hidden requirements, an inherited codebase, a flaky REST API, and a serving budget. It must ship a customer-service agent, which is then scored against held-out simulated users. 53 tasks (airline+, retail+, telecom, banking_knowledge). Best: Opus 5 + Claude Code 23.9%; expert ceiling 82.2%. Failure modes: shallow keyword queries over records, almost no talking to the client, ships the first design that runs. | MIT, github.com/sierra-research/hyper-tau-bench. Needs Docker and OpenRouter/OpenAI keys. Build trajectories are saved locally; the leaderboard has a trajectory visualizer. | Motivation and citation only. Too heavy to run in a day. |
| **CL-Bench** (arXiv 2606.05661, Berkeley/Snorkel) | Continual learning across instances that share hidden structure. *Database Exploration*: 40 NL questions on an obfuscated SQLite DB (e.g. `g2_reviews`, `vrf` = verified, prices in cents for one group and dollars elsewhere). 15-query budget; reward = fraction of budget saved. **Schema migration at Q20** creates concept drift. **Gain metric** = stateful minus stateless reward per instance. Plain ICL beat dedicated memory systems. Claude Code gain on DB Exploration: 43.6%. | continual-learning-bench.com | **Best template.** Port it to MongoDB. |
| **τ²-bench** (Sierra) | Customer-service agent with a user simulator, domain policy, and tools. Airline, retail, telecom. | Code on GitHub; community trajectories on HF (e.g. zero-proof-ai/tau2-simulated, 1,057 graded convos) | Viable but costly and noisy. The user simulator is an LLM, and each task is multi-turn. |
| **FDE-Bench** (arXiv 2609.27571) | 136 deployment-config tasks (Docker/K8s/health). Graded in 4 layers: build → ready → behavior → conformance. Best 75.0%. | MIT; ~30-task public dev split | Off-theme. It tests infra config, not memory. |
| **Trains but Doesn't Learn** (arXiv 2609.25237, EMNLP'26 Industry) | FDE delivering post-training as a service through 10 stages with a human-approval gate. Failure mode: loss falls, everything looks green, but the model is no better. | No release found | Framing only. The "self-report ≠ truth" gate matches H9. |
| **EvoHarnessBench** (arXiv 2609.04280, Salesforce) | The harness (tools/skills/agents) grows over 17 streams / 802 tasks. Finding: **harness-induced forgetting**. | Project site | Supports keeping regression evals in the gate. |

### Discovery ground truth inside hyper-tau-bench (checked in the repo, 2026-09-26)

The FDE's first step is discovery: reconstructing the customer's real operating rules from many scattered, conflicting sources. τ^τ-bench builds its corpora exactly that way. Each domain's policy is split into **atomic facts with IDs**, and the facts are then rendered into business artifacts. Both the facts and the artifacts are in the repo (`data/tau2/hyper/sops/`):
- **Gold facts:** `sections/<section>/schema.json` → `facts: [{id: "F002", statement: ...}]`. Example: banking `credit_limit_increases` has 106 facts.
- **Evidence corpora:** `evidence_corpus_{hard,deep}_001/`. The same banking section has 109 artifacts: 44 support cases, 15 emails (.eml), 15 website pages, 8 meetings (.vtt), 7 presentations, 7 flowcharts, 3 Slack dumps, and 2 each of Jira, KB, ledger, and helpdesk exports. About 20+ banking sections, plus airline_plus, retail_plus, and telecom. The airline hard pack has 377 artifacts.
- **Answer key per artifact:** `eval_manifest.json` lists each artifact's `authoritative_fact_ids`, a `status` of **`final_current` / `superseded` / `context_only`**, and `fact_renditions` (how the fact is phrased in that source). This gives ground truth for recall, citation, and supersession.
- **Client-only facts:** e.g. `airline_plus/variants/core_evidence_bundle_hard_client_001.json`. 17 facts live only with the simulated client, including "deliberately contested readings" and a "stale grace-window succession". This makes elicitation measurable.
- Paper: the corpora were audited so that artifacts introduce nothing beyond their assigned facts. So an extracted rule with no matching gold fact is very likely a hallucination.
- Artifact counts per manifest domain: airline_plus 27, banking 40, retail_plus 12, telecom 75.
- **Fact → carrier map for every artifact:** `evidence_corpus_*/transformation_pack.json` → `transformations[].artifacts[]` has `included_fact_ids`, `depends_on_fact_ids`, `context_only`, and presentation `page_fact_ids`. The bundle lists all fact_ids (credit_limit_increases: 106 facts, 14 transformations). The corpus is described as "a dated … evidence room". Meeting filenames and email headers carry dates, which is enough to compute *when each fact first became decidable*. Staleness traps exist, e.g. a KB article revision marked `retired_2025-09-02`: "its empty-response claim is the staleness trap".

### 3c. Benchmark direction under discussion (2026-09-26): time to trusted decision

The goal is to **shorten time to decision and reduce rollbacks**. The agent fills a **fixed, typed decision record** for every customer, following **fixed grounding rules**. The reviewer/client is a **scripted, deterministic oracle**, and grading is exact typed matching, so the agent is the only stochastic factor. Metrics on an evidence clock: time to trusted decision per slot, lag vs decidable-at, rollbacks (premature / stale-trap / pushback-induced flips), silent errors, reviewer units. Not yet approved; the record's slots are under user review.

Supporting notes:
- [`research/notes/deterministic_eval.md`](research/notes/deterministic_eval.md). LLM user simulators and judges add variance: τ² has 12–13% critical user-sim errors, and changing the user LLM swings scores up to 9 pts. Evidence:
  - SGD and MultiWOZ show label noise costs about 10–18 JGA. This is why gold is re-derived from the spec.
  - ConflictBank and FRESCO show recency bias and stale-passage errors. This is why arrival order is decoupled from effective date.
  - FlipFlop: models flip 46% of the time under "are you sure?". This is why the reviewer is strictly accept/reject.
  - Use τ-bench pass^k across seeds, and an AutoDL-style anytime AUC.
- [`research/notes/synthetic_customer_corpora.md`](research/notes/synthetic_customer_corpora.md). Generation recipe: a hand-typed spec is frozen first; code renders structured artifacts; the LLM writes prose only. The CI audit checks:
  - every fact is recoverable through the agent's tools;
  - no distractor changes gold;
  - lazy solvers fail the traps: first-mention, latest-doc, and corpus-only (never ask the client);
  - a surface-feature classifier can't find the carrier (AUC ≈ 0.5);
  - there are no synthetic tells;
  - the corpus is hash-frozen.
  
  Sources: τ^τ-bench, Era by Eon, AgentMercury, EnterpriseRAG-Bench, WinSyn.
- [`research/notes/fde_discovery_practice.md`](research/notes/fde_discovery_practice.md). All 11 draft slots are supported by practice. Proposed changes:
  - add `decision_owner/stakeholders` and `in_scope_use_cases`;
  - merge the approval threshold into `forbidden_actions`;
  - add `source_ref`, `as_of`, and `confidence` to every slot.
  
  Rework evidence: PMI says 37–39% of project failures stem from inaccurate requirements; MuleSoft says 80% name data integration as the top obstacle. Neither gives a breakdown by cause.
- [`research/notes/fde_testimony.md`](research/notes/fde_testimony.md): first-person FDE accounts tested against the user's 4-area frame (data inflow; SOP/policy incl. shadowing; who we build for; metrics).
  - **Data inflow:** strongly supported, ~8 sources. Access is the longest pole: an 8–12 week pilot went entirely to data access, and Stanford's 51-deployment study says success "required access", not centralization.
  - **SOP/shadowing:** strongly supported, ~10 sources. Shadowing evidence is mostly from Palantir alumni; CX-agent companies instead convert written SOPs and review conversations daily.
  - **Who we build for:** supported for end user vs sponsor; weaker for an approver/ops-owner split.
  - **Metrics:** supported as an area, but **"95% typical" is not supported**. Sponsors accepted 80–85%. Regulated industries raise the bar via **mandatory human review and deterministic checks**, not a higher number. Resolution/containment 70–90%; Fin $0.99/resolution vs "$5–15" human (snippet); AHT evidence is vendor-only.
  - **Outside the 4 areas:** security/access, scope/problem selection, autonomy/escalation level, eval-set ownership, go-live, change management.
  - **Reversals:** stated problem ≠ real problem; data access eats the timeline; accuracy bar renegotiated down with human review added; unclear policy churns requirements.

---

## 4. Implications for design

### 4.1 Revised cross-model hypothesis
> A harness is co-adapted to the **runtime model whose trajectories it was evolved on**, not to the model that authored it (U1, H2, H4). Co-adaptation lives in the **control/model-bound layer**: budgets, stop rules, prompt phrasing, tool protocol. **Customer truth** (workflow facts, policies, evals, validators) is portable (§3.5, Self-Harness convergence, U1 "procedurally isomorphic" skills). Portable ≠ usable: weaker runtimes may not load or follow it (U4, U5).

Consequences:
- **Any model can be the proposer.** Use a cheap one (U1). Spend budget on the runtime agent and on eval.
- **Key every version as `(harness_version, runtime_model)`.** A model swap or upgrade is a non-stationarity event: re-run the eval, and recalibrate only the model-bound layer.
- **Split each accepted mutation into an *intent* (portable) and an *implementation* (per model).** This follows Self-Harness: the same goal, implemented differently per model.
- **Cross-deployment promotion (docx §9)** must check whether a recurring mutation recurs because of *customers* or because of *the model*.

### 4.2 Changes to the docx design

**Split procedural memory into two layers:**
```
customer_harness/
  truth/      # portable: workflow.md, policies.md, known_exceptions.md, evals/, validators/, retrieval sources
  binding/<runtime_model>/   # model-bound: prompt phrasing, step/token budgets, stop rules, tool-call format
  anchor/     # FDE-owned, agent cannot edit (HSI): guardrails, permissions, scoring harness
```

**Additions to the mutation schema:**
| Field | Source |
|---|---|
| `runtime_model` | H4, §3.5 |
| `layer: truth \| binding \| anchor` | §3.5 |
| `applicability_condition` (required) | HarnessCompass — fixes overgeneralization |
| `predicted_fixes`, `risk_cases` | HarnessCompass manifest |
| `falsification_criterion` | HSI |
| `activated_in_runs`, `load_rate`, `adherence_rate` | H7, U4/U5, DemoEvolve, HarnessBank |
| `fixed_case_ids`, `broken_case_ids` | SEAGym, Evo-Bench |
| `delta_vs_noise_band`, `significance_z` | H5, Evo-Bench, HarnessBank |
| `fde_edit_diff`, `fde_edit_distance` (normalized) | PRELUDE/CIPHER, Harness-R1 |
| `fde_rationale`, `reject_reason: wrong \| preference \| out_of_scope \| unsafe` | ARIA, Copilot-feedback 37.2% |
| `superseded_by` | ARIA |
| `evidence_weight` (recomputed as the component changes) | DREvo |

### 4.3 Pipeline: proposal → FDE → promotion

1. **Diagnose** on structured traces linked to harness artifacts (HarnessFix 55→85% localization). Pull raw traces on demand (Meta-Harness).
2. **Automated gates before the FDE sees anything** (HarnessBank): valid → no leakage or hard-coded cases → **actually fires** → delta outside the customer's noise band → no regressions on the replay set.
3. **FDE review** shows evidence, diff, fixed and broken cases, and applicability condition. The FDE picks accept / edit / reject / defer, with a reason tag.
4. **Promotion is decided only by a held-out split the proposer never sees** (HarnessDev H6, HarnessOpt-Bench tiers). Never use proposer confidence (priority ranking: self-prediction ≈ chance).
5. **Auto-track the best version; rollback is one click.** Removal counts as a real mutation (H11).
6. **Survival tracking:** later fate, `superseded_by`, evidence weight decays as components change (DREvo), utility-style pruning (ReMe).

### 4.4 Learning the mutation policy (roadmap)
- **V0 (no training):** retrieve prior mutations for the same component or failure pattern, with verdicts, FDE diffs, and reasons. Use FDE-edited versions as few-shot examples. Demonstrate the docx §11.3 sequence: fewer repeated overgeneralizations, and FDE edit distance falling over time.
- **V1:** reweight evidence (DREvo), and archive mutations by component × failure pattern (HarnessBank).
- **V2 (needs data pooled across deployments):** supervised fine-tuning on accepted and edited patches, then preference learning from (proposal, FDE edit) pairs (Harness-R1: about 1,500 failure batches × 8 candidates).

### 4.5 Experiments this enables (contribution candidates)
1. **Survival by layer across a model swap:** evolve a customer harness on model A, swap to model B, and measure survival per layer. Prediction: truth mutations survive; binding mutations don't. Report **re-adaptation cost** (mutations or FDE actions needed to recover).
2. **Matched-budget baselines none of the papers ran:** (a) retry the unchanged harness, (b) **random mutation**, (c) automated evolution without an FDE, (d) FDE-gated evolution.
3. **Does FDE gating fix final-version selection?** HarnessDev shows only 2/9 self-selected versions were held-out optimal, and evolution loses to doing nothing at matched budget (Rethinking). Test whether human selection plus the gates close that gap.

### 4.6 Corrections to the docx
- **ReMe:** the "8B + ReMe beats memoryless 14B" claim isn't true on every metric (BFCL-V3 Avg@4: 45.17 vs 48.66). Qualify it.
- **Letta Context Repositories:** it's a blog post (Feb 2026), not a paper. It has no utility pruning and no human approval.
- **§14 novelty:** add HarnessDev, Self-Harness, HarnessCompass, Meta-Harness, and ARIA as closest neighbors. Frame as "to our knowledge". HarnessDev §2 explicitly names FDE work and studies only the execution-system layer.
- **§11 evaluation:** add a noise band, matched-budget baselines, replay/forgetting checks, and a model-swap condition.

---

## 5. Build spec: problem framing, eval, architecture (decided 2026-09-26, for review)

Status: **draft for review.** It combines decisions made in discussion with the user. Items marked ⚠ still need a user decision (§5.8).

### 5.1 Problem framing (decided)

FDE discovery has two phases:
1. **Onboarding/mapping:** finding out *what sources exist and where*, mostly by asking people. **Out of scope.** It depends on human access, is hard to simulate, and is hard to score. It is **given as an input** to the eval.
2. **Discovery and investigation:** given a rough list of sources, work out **which ones are useful and where inside them the useful signal is**, then turn findings into harness changes. **This is the task.**

The core difficulty is *not knowing what is useful or where it is*, across mixed quantitative and qualitative sources (records, QC sheets, docs, interview transcripts). Sources may conflict, but conflict is only one possible finding. Tech-stack and codebase variation is out of scope.

Two things evolve, and both are versioned, gated, and reviewed by the FDE:
- **What the agent knows about the customer:** the truth layer (rules with `applies_when`, exceptions, eval cases).
- **Where it looks for this customer:** the retrieval/investigation policy, meaning which sources and fields to check first for which case types. This is the docx's "retrieval policy" mutation class, and it's learned from provenance of changes that survived.

### 5.2 Eval domain (decided, pending ⚠ confirmation)

- **Workflow:** compliance alert triage (AML / transaction monitoring style). Input: alert + related records. Output: a disposition in `{close_false_positive, request_info, escalate}`, graded by **exact match** against the answer key. Deterministic grading keeps the noise band small; noise comes only from the model.
- **Customers:** three companies, **same workflow family, different industries**: bank, fintech, online gambling operator. We chose *slightly different* over *very different*:
  - it isolates what varies (sources, where signal lives, local rules, data conventions);
  - it matches FDE reality (one base harness, many customers);
  - it's required for the cross-deployment "local vs base" question;
  - a very different workflow confounds domain difficulty with discovery ability, and triples build cost.
- **Optional 4th customer:** a marketplace doing refund-abuse review, as a *very different* generalization probe. Stretch goal only.
- **All data and rules are synthetic, fictional but plausible, and labeled as such.** They are not claims about real regulations.

### 5.3 Per-customer dataset (to generate)

Each customer is generated from a **seeded generator plus an answer key**. Records are generated in code. Qualitative text (interviews, QC comments, SOP prose) is generated by an LLM *from* the answer key and then checked, so every planted signal is actually present and nothing extra is.

| Component | Contents |
|---|---|
| **Source manifest** (given) | Source ids with `described_as`, meaning what the customer *says* during onboarding. **Deliberately noisy:** it includes ≥1 plausible but irrelevant source and ≥1 wrong description (e.g. "wiki is up to date" when it isn't). The manifest says what exists, **never what's useful.** |
| **Records** | Alerts, transactions, accounts/players. Cryptic field names and customer-specific conventions (e.g. amounts in cents, status codes whose meaning differs from the docs, per-player vs per-account IDs). |
| **QC sheet** (where present) | A sample of past alert decisions with reviewer scores and free-text comments. It's the source of labels, and reviewers are sometimes noisy. |
| **Docs / SOP** | The official process. Partly stale, and ≥1 policy change is recorded only elsewhere (Slack/notes). |
| **Interview transcripts** | 2–3 per customer (e.g. analyst, lead, new hire). The recorded *output* of onboarding. They contain tacit exceptions. |
| **Customer-contact oracle** | Answers targeted questions ("what does `adj_cd=7` mean?") from the answer key. Each question costs budget. Unknown or irrelevant questions return "don't know". |
| **Answer key** | For each **planted signal**: its location (source + field/passage), meaning, correct scoped rule (`applies_when`), affected cases, and whether it's **customer-specific** or **shared**. |

**Source mix differs per customer (illustrative):**

| | Bank | Fintech | Gambling |
|---|---|---|---|
| Sources | rich records, formal QC sheet, long SOP | thin SOP, Slack/ticket notes, **no QC sheet** | QC sheet, player activity records, interviews |
| Main signal location | QC reviewer comments | a cryptic transaction field | an interview remark plus an activity pattern |
| Local twist | strict escalation thresholds | policy change mid-stream | industry-specific checks (source of funds, responsible-gambling flags) |

**Planted signals:** 4–6 per customer. **≥1 pattern is shared across all three** (it should be proposed for the base harness), and the rest are customer-specific (they should stay local). That gives an answer key for docx §9's "customer-specific vs reusable" question. We're not aware of any benchmark that currently measures that.

### 5.4 Episode protocol

```
for customer in customers:
  harness = base_harness                              # same starting point for every customer
  for batch t in 1..T (T≈3):                          # cases revealed over time, not all at once
    run the runtime agent on batch t → failures + traces
    investigation agent: probes (query / read / ask the oracle), all logged with cost, within budget B
      → findings (linked to evidence) → proposals (one hypothesis each, scoped)
    gates (validity → lint → fires → beats noise band → replay) → FDE decision → promote / reject
    update per-source usefulness from the provenance of surviving changes
  evaluate on the holdout split after each batch
```

- **Splits per customer:** `diagnostic` (traces visible), `selection` (only the aggregate score visible), `holdout` (never visible), `replay` (previously passing cases).
- **Noise band:** re-run the unchanged harness K≥3 times per (customer, runtime model).
- **FDE for eval runs:** ⚠ see §5.8. A **simulated FDE policy** driven by the answer key:
  - accept if the proposal matches a planted signal with the correct scope;
  - edit and narrow if it's too broad;
  - reject if it isn't supported;
  - pick a reason tag.
  
  In the live demo, a real human plays the FDE.

### 5.5 Metrics

| Metric | What it shows |
|---|---|
| Findings recall / precision vs the answer key | Discovery quality |
| Probes and cost until each planted signal is found | Efficiency. Also: share of budget spent on irrelevant sources. |
| Holdout disposition accuracy per batch, delta vs noise band | Does the harness actually get better? |
| Survival rate of accepted changes; fix/forget counts on replay | Durability, regressions |
| **Batch t+1 with learned source usefulness vs without it** (CL-Bench-style gain) | **Headline: "it learned where to look"** |
| FDE edit distance over batches | Proposer gets less wrong (docx §11.3) |
| Local vs base classification accuracy on planted shared/specific signals | Cross-deployment signal (docx §9) |

**Baselines:**
1. static base harness;
2. matched-budget retry of the unchanged harness;
3. **matched-budget random mutation** (none of the papers we read ran this);
4. automated evolution without the FDE gate, i.e. auto-accept everything that passes the gates;
5. full system.

For a one-day build: 1, 2, and 5 are required; 3 and 4 are stretch goals.

### 5.6 Architecture mapping (unchanged kernel; new discovery layer)

| Component | Role | New? |
|---|---|---|
| Source manifest + source profiles | Cheap per-source profile (schema/field stats, QC dimensions, doc/interview topic summaries), embedded | new |
| **Investigation agent** | Starts from failures and asks "what separates wrong cases from right ones?". Runs contrast aggregations over records and vector search over qualitative text. Uses the oracle when stuck. Every probe is logged. | new |
| Findings / claim ledger | Finding → evidence links (stance; n/N for quantitative, quote for qualitative) → status | new (slimmed from §4) |
| Per-source usefulness | Credit from provenance of **surviving** changes → retrieval-policy mutations | new |
| Runtime agent, proposer, kernel gates, FDE UI, survival, rollback | As in §4.3 and `.claude/rules/harness-evolution.md` | unchanged |

Atlas collections added: `source_manifests`, `source_profiles` (vector), `evidence` (vector), `probes`, `findings`, `source_usefulness` (derived).

### 5.7 Build order (one day, submissions due 22:00 EDT)

1. Data generator + answer key for **one customer** (bank). Manifest, records, QC sheet, SOP, 2 interviews, oracle.
2. Version store (content hash, pointer rollback + test) and proposal schema.
3. Runtime agent (triage) + holdout/replay eval + noise band.
4. Investigation agent (contrast queries + vector search + oracle) + probe log.
5. Gates (validity, lint, fires, noise, replay) + simulated FDE + FDE review UI.
6. Batch loop over T=3 + metrics + "with vs without learned source usefulness" comparison.
7. **Stretch:**
   - customers 2–3 (fintech, gambling) + shared-signal classification;
   - baselines 3–4;
   - model-swap re-validation.

### 5.7b Base harness (research → [`research/notes/base_harness.md`](research/notes/base_harness.md); recommendation pending user OK)

- **No usable open-source AML/KYC triage agent exists.** Hits are 0–2★ solo repos from 2026, mostly unlicensed. FINOS hits aren't agents. Jube, Marble, and Tazama are rule/ML monitoring engines, not LLM agents.
  - Best to *borrow ideas* from: `ameshram/agentic-alert-triage` (MIT). Actions ≈ ours. LLM tool loop + a separate rule-based `policy.py` makes the final call. Has a false-negative-rate eval gate and a synthetic data generator. Not LangGraph and Anthropic-only, so borrow patterns, not code.
- **Top pick: LangChain Deep Agents (`deepagents==0.7.19`, MIT; pin it, released daily).** Built on LangGraph, so the MongoDB checkpointer and store plug in. Its native extension points map onto our mutation classes:

  | Our mutation class | Deep Agents extension point |
  |---|---|
  | context | `AGENTS.md` |
  | skills | `SKILL.md` folders, with customer-over-base layering |
  | tools, control | tools, middleware hooks |
  | anchor | human approval, file permissions |

  OpenRouter support is built in (`langchain-openrouter`). A harness version = a git-diffable folder or a MongoDB-store namespace.
  - **Watch-outs:**
    - Hide the built-in file/shell/subagent tools (token cost).
    - Give the runtime agent **read-only** file access to its own harness (kernel/surface invariant).
    - Don't use MongoDB's official Deep Agents adapter (it stores files on S3).
    - Unverified: the `openrouter:` string form. Pass a model instance instead.
- **Runner-up: LangChain v1 `create_agent` plus a ~100-line file loader.** Same hook API, less magic, fewer tokens. Switch if Deep Agents costs more than about an hour.
- **Also borrow:**
  - tau2-bench's per-domain layout (`policy.md`, `db.json`, `tasks.json`, `tools.py`);
  - Meta-Harness (`stanford-iris-lab/meta-harness`, MIT) text-classification seed harnesses and its proposer loop;
  - Self-Harness's held-in/held-out acceptance gate (idea only; the repo has no license).
- HarnessDev's GitHub repo is empty. HarnessCompass has no public code. VeRO is MIT but built on Harbor, which is too heavy for today.

### 5.8 Open decisions (need user input)

**User answers (2026-09-26 ~12:00 EDT):**
- **Domain:** accepted as the rough eval shape. **Don't build the base agent harness from scratch.** Adopt an existing open-source base harness (research in `research/notes/base_harness.md`).
- **FDE:** a **simulated FDE** defined by rules, scripts, and a persona. It's used for eval runs.
- **LLM budget:** **$10 on OpenRouter** in total. The user will supply the key.
- **Model switch:** not in the MVP. Show it in the UI as a *future goal* only.
- **Infra:** MongoDB is required. Atlas access is not yet verified (see chat).
- **Team:** solo. Git is approved.

Original questions:

1. **Confirm the domain:** compliance alert triage × bank / fintech / gambling, with a shared signal planted alongside customer-specific ones.
2. **FDE in eval runs:** a simulated FDE policy driven by the answer key for batch runs, with a live human only in the demo? (Recommended; a human can't review every proposal × 3 customers × 3 batches today.)
3. **Models and budget:** runtime and proposer models via OpenRouter, and a cost cap for eval runs. Noise band K=3 × cases × batches × customers adds up.
4. **Model-swap re-validation:** MVP or stretch? (Recommended: stretch.)
5. **Infrastructure readiness:** is an Atlas cluster available, with Vector Search, and is Automated Embedding available on it? Is the OpenRouter key set? Or start on the local `mongodb-atlas-local` container?
6. **Team split:** how many people, and who takes which part (data generator / agent + kernel / UI)?

### 5.9 Design lock: memory and rewrite (brainstorm, confirmed by user 2026-09-26)

**Three separate things (don't conflate them):**
1. **Dev setup:** `CLAUDE.md` and `.claude/` guide Claude Code while it builds.
2. **Product harness:** each customer's triage-agent units, stored in Atlas.
3. **Product kernel:** gates, backtest, promotion, and DB permissions, as code.

This section specifies #2 and #3.

**Understanding summary**
- **What:** per customer, a mid-tier triage agent (Deep Agents) runs on an FDE-approved harness of structured units.
  - An investigator finds useful signal in known but unmapped sources.
  - A proposer turns findings into single-unit changes.
  - Gates and a backtest filter the changes.
  - A simulated FDE accepts, edits, or rejects them.
  - The kernel versions and promotes.
- **Why:** show the harness learns *what's true* and *where to look* per customer, and that its changes survive later evidence.
- **For:** hackathon judges (Atlas, Vector Search, agentic memory); later, FDE teams.
- **Constraints:** solo; due 22:00 EDT; $10 OpenRouter; Atlas M10 sponsor sandbox; Deep Agents; synthetic data.
- **Non-goals today:**
  - onboarding/mapping (the manifest is given);
  - tech-stack variation;
  - model-swap re-validation (UI placeholder only);
  - full base-harness evolution;
  - a trained proposer;
  - automatic rollback.

**Memory map**

| Memory | Contents | Writer | Reader |
|---|---|---|---|
| Run state (LangGraph checkpointer) | one triage run | runtime | runtime |
| Procedural = harness | versioned **structured units** (rules w/ `applies_when`, skills, hooks, lookup policy) → rendered to Deep Agents files | **promotion only** (FDE action) | runtime |
| Episodic (append-only) | traces, probes, proposals, gate/backtest results, FDE decisions, fates | all append; no edits | investigator, proposer, UI |
| Semantic / evidence (vector) | source profiles, evidence chunks, findings w/ provenance | investigator | investigator, proposer (**not runtime**) |
| Derived views | live pointer, investigator source priors, survival | kernel (recomputed) | all |

**Decision log**

| # | Decision | Alternatives | Why |
|---|---|---|---|
| 1 | Runtime sees **only the approved harness** | hybrid recall; tiered | every behavior change traces to a version |
| 2 | Harness = **structured units** (id, hash, `applies_when`, layer), rendered to Deep Agents files; version = set of unit hashes | whole files; hybrid | survival and supersession per rule |
| 3 | Investigator source priors = **automatic derived view** from survival; shown, not gated. The runtime lookup policy stays a gated unit. | gated; override | already grounded in FDE decisions |
| 4 | Simulated FDE = **reactive checker** with the answer key. Accept / narrow `applies_when` / reject using deterministic scripts; persona text is templated. Never adds knowledge nobody proposed. | partial knowledge; noisy (noise setting can be added later) | gains must come from the agent, not the FDE |
| 5 | Proposer recall is **same customer only**. Cross-customer synthesis runs downstream and proposes to the base harness. **Base and customer harnesses never evolve at the same time.** | all customers; lessons only | clean attribution; realistic |
| 6 | Cross-customer synthesis = **stretch goal** (group surviving changes → base proposals → score vs the planted shared signal) | UI only; full | uses the shared-signal answer key if time allows |
| 7 | **Backtest before rollout** (replay of all seen cases + holdout, vs noise band). Changes leave only through a supersede/retire proposal (also backtested) or an FDE revert. **No auto-rollback; only FDE actions move the live pointer.** | flag→FDE; auto-rollback | matches real rollout practice |
| 8 | **Mid-tier model runs the loop.** A strong model runs (a) a **calibration check**: strong + base harness must *not* solve the planted-signal cases, and (b) the final comparison (strong + base vs mid-tier + evolved). | single tier | don't build something a strong model solves anyway |
| 9 | **Triage sees only its own case.** Dataset rule: **no planted signal can be solved from a single case.** Each needs cross-case or cross-source evidence. | all sources; case + retrieval | isolates the loop's value |
| 10 | **Two customers in the MVP:** bank (dev) + fintech (**held-out**, config only; git tag `freeze-before-fintech`; no looking at fintech traces while developing). Gambling = stretch. | one customer | a single customer is likely to overfit |
| 11 | The two customers differ in **source mix, signal location, signal type, decoys, disposition base rates, label source, and vocabulary/schema** (matrix in chat, 2026-09-26). A **difference audit** in the generator allows no shared signal except the one shared signal. | cosmetic differences only | otherwise "read QC first" gets hard-coded and fintech proves nothing |

**Customer difference matrix (decision 11)**

| Axis | Bank (dev) | Fintech (held-out) |
|---|---|---|
| Sources | case records, formal QC sheet, long SOP, 2 interviews | txn records, **no QC sheet**, thin SOP, Slack/ticket notes, 2 interviews |
| Signal home | QC reviewer comments (cross-case patterns) | cryptic record field + Slack |
| Signal types | SOP scope error; QC-only convention; interview-only tacit exception; definition mismatch (resolved ≠ `closed`); shared | cryptic code explained only by the customer contact; mid-stream policy change (Slack, not SOP); cents convention; threshold visible only in record statistics; shared |
| Decoys | billing export | marketing analytics dump; SOP described as "up to date" but stale |
| Dispositions (close / info / escalate) | ~60 / 25 / 15 | ~40 / 20 / 40 |
| Labels from | QC-reviewed dispositions | outcomes (chargebacks, confirmed fraud) |
| Vocabulary | `case`, `account`, formal fields | `txn`, `wallet`, abbreviated fields |

**Improvement evidence (within customer, batch 1→3):**
- holdout accuracy per version vs the noise band;
- vs static base and matched-budget retry;
- vs strong model + base;
- batch 3 investigation with vs without learned priors (probes, budget spent on decoys);
- FDE edit distance and reject rate over batches;
- survival.

**Generalization:** the same metrics on the held-out fintech, with no tuning. Each planted signal must affect about 10–15% of holdout cases so it moves accuracy past the noise band.

**Assumptions (defaults)**
- About 150 alerts per customer: 3 batches of about 30, holdout of about 40, plus replay. 4–6 signals per customer.
- At most 3 proposals per batch. Noise band from K=3 runs.
- Batch cycle finishes in under about 10 minutes.
- **Cost:** LLM cache keyed by input hash; spend counter with a hard stop at $9. Estimate: about $3–4 for the loops, $1–2 for strong calibration and comparison, the rest as buffer.
- **Security:** DB users `fde_app` (`readWrite` on `fde_harness`) and `fde_proposer` (read + insert on `proposals` only), both scoped to Cluster0. Secrets live in `.env` / `secrets/`, are never logged, and there is no PII.
- **Reliability:** runs are checkpointed; retries; infrastructure failures are never blamed on a proposal.
- **Embeddings:** Voyage, via Atlas Automated Embedding if available, else the Voyage API directly. Model and dimension are recorded with the index.
- **Maintenance:** kernel tests (versioning, gates, promotion); everything else best-effort.

**Open:**
- Exact OpenRouter model IDs (picked at build time from the live list).
- Whether Atlas Automated Embedding is available on the cluster.
- The user must approve the suggested edit to the dev rule `.claude/rules/harness-evolution.md` (auto-rollback conflicts with decision 7).

---

## Sources
- HarnessDev — https://arxiv.org/abs/2609.01437
- Harness Updating Is Not Harness Benefit — https://arxiv.org/abs/2605.30621
- HarnessFix — https://arxiv.org/abs/2606.06324
- Harness-R1 — https://arxiv.org/abs/2608.02276
- DemoEvolve — https://arxiv.org/abs/2605.24539
- VeRO — https://arxiv.org/abs/2602.22480
- Meta-Harness — https://arxiv.org/abs/2603.28052
- HarnessCompass — https://arxiv.org/abs/2608.01918
- DREvo — https://arxiv.org/abs/2607.26722
- Hierarchical Self-Improvement — https://arxiv.org/abs/2608.08466
- HarnessBank — https://arxiv.org/abs/2607.13683
- Rethinking the evaluation of harness evolution — https://arxiv.org/abs/2607.12227
- SEAGym — https://arxiv.org/abs/2606.17546
- Evo-Bench — https://arxiv.org/abs/2608.09096
- HarnessOpt-Bench — https://arxiv.org/abs/2608.06301
- Priority ranking — https://arxiv.org/abs/2605.22505
- Harness-Bench — https://arxiv.org/abs/2605.27922
- Self-Harness — https://arxiv.org/abs/2606.09498
- PromptBridge — https://arxiv.org/abs/2512.01420
- ARIA — https://arxiv.org/abs/2507.17131
- Copilot feedback in customer support — https://arxiv.org/abs/2604.23855
- ReMe — https://arxiv.org/abs/2512.10696
- (PRELUDE/CIPHER, Airbnb AITL, Letta Context Repositories — links in `research/notes/human_in_loop.md`)
