# Evaluation rigor for harness evolution — reading notes

Context: self-evolving FDE deployment harness (agent proposes versioned mutations; FDE accepts/edits/rejects; key metric = mutation survival). Prior anchor: HarnessDev (arXiv 2609.01437): evolution gains mostly within noise (±4.75 pts), feedback-set vs held-out agree 53%, self-selected final versions rarely held-out optimal.

Method: all five PDFs downloaded from arxiv.org/pdf/<id> and full text extracted with pypdf (2026-09-26). Numbers below are copied from the extracted text; any gaps are flagged.

---

## 1. Rethinking the Evaluation of Harness Evolution for Agents (arXiv 2607.12227)

- Citation: Yike Wang*, Huaisheng Zhu*, Zhengyu Hu, Yige Yuan, Zhengyu Chen, Shakti Senthil, Hannaneh Hajishirzi, Yulia Tsvetkov, Pradeep Dasigi, Teng Xiao*. AI2 / UW. arXiv:2607.12227v2, 27 Aug 2026.
- URL: https://arxiv.org/abs/2607.12227 (code: github.com/rethinking-harness-evolution)
- Read: full text (13 pp.).

### Setup
- Benchmark: Terminal-Bench 2.1 (89 tasks; 28 repaired vs TB 2.0). Models: Claude Opus 4.6, GPT-5.4, GPT-5.4 mini, high reasoning, 128k gen budget. Results averaged over **2 independent runs**.
- Four methods under a matched budget K=5: (a) Parallel Sampling (fixed harness, K independent tries, select by self-judge or unit test), (b) Sequential Refinement (fixed harness, each try conditioned on summary of previous), (c) Harness Evolution = AHE (Lin et al. 2026) with its "explore agent" disabled (it retrieves benchmark-specific harnesses externally = leakage), m=1 rollout per task per harness, (d) Harness Scaling = per-instance harness adaptation.
- Initial harness: single bash tool only, no skills/middleware/memory.
- Infra failures (sandbox crash, API timeout) scored as 0, not excluded.

### Key numbers
- No unit tests (self-judge only), pass@1 (Opus/GPT-5.4/mini/avg): initial 69.9/75.3/59.4/**68.2**; Parallel Sampling 74.7/79.2/62.9/**72.3**; Sequential Refinement 73.0/73.0/61.8/69.3; **Harness Evolution 71.4/69.7/61.3/67.4** (below baseline on avg; GPT-5.4 drops 75.3 -> 69.7); Harness Scaling 76.0/78.1/61.2/71.8.
- With unit tests (Opus, GPT-5.4; avg): initial pass@1 72.9; Parallel Sampling pass@1 86.0 / pass@5 86.0; Sequential Refinement 84.3 / **91.8**; Harness Evolution **75.8 / 86.2**; Harness Scaling 82.6 / 89.3. Harness evolution barely beats direct sampling on pass@1; gains appear only when selecting among multiple attempts.
- Held-out generalization: split 45 train / 10 val / 34 test; evolve on train, select on val, report test. Initial 63.3 (Opus) / 72.1 (GPT-5.4) / avg 67.7 -> evolved 64.5 (+1.2) / 72.1 (+0.0) / 68.3 (**+0.6**). "Strong tendency to overfit the search set."
- Qualitative: edits are "rational" (prompt rules -> middleware enforcement like turn-budget trackers, finalization gates -> tool guidance), but "most edits memorize fixes rather than distilling strategies" (task-specific facts, command orders, dataset properties embedded in prompt); stable core of hard failures unaffected; growing prompt text causes context bloat.

### Recommended protocol
- Compare harness evolution against **test-time scaling baselines at matched feedback and inference budget** (parallel sampling w/ same K, sequential refinement). Spell out what feedback each method gets.
- **Separate optimization feedback from final measurement**: disjoint train/val/test; select harness on val, report on untouched test.
- Report pass@1 separately from pass@k; a real harness improvement should show up in pass@1, not only best-of-k.
- Disable components that retrieve benchmark-specific solutions (leakage).
- Count infra failures as failures. Average multiple runs (they used only 2 — still thin).
- Use benchmarks with headroom and genuine harness sensitivity (TB may be insensitive to harness).

### Implication for us
- Every mutation proposal needs a **matched-budget counterfactual**: "would just retrying / best-of-K with the current harness have fixed this case?" If yes, the mutation is not a harness improvement.
- Tag mutations that embed customer-case-specific facts (paths, command sequences, record counts) as **memorization** vs. strategy; memorization mutations should be scoped (e.g., per-case notes / memory) and not counted as harness wins. Watch prompt bloat as a cost.
- Promotion must use tasks the proposer never saw; with a tiny held-out set, +0.6 to +1.2 pt gains are indistinguishable from noise.
- Self-judged improvement (no external verifier) actively hurt a strong model — FDE judgment / a real verifier is the grounding signal; do not let the proposer self-certify.

---

## 2. SEAGym: An Evaluation Environment for Self-Evolving LLM Agents (arXiv 2606.17546)

- Citation: Congjie Zheng*, Chuanyi Xue*, Bin Liang, Jun Yang, Changshui Zhang. Tsinghua University. arXiv:2606.17546v1, 16 Jun 2026.
- URL: https://arxiv.org/abs/2606.17546
- Read: full text incl. appendices (32 pp.; some figure content not extractable).

### Setup
- RL/MDP-style environment over agent snapshots A_t = (fixed model M, mutable harness H_t); update rule H_{t+1} = U(H_t, B_t, T_t, F_t). Built on Harbor (containerized tasks + verifiers). Separates rollout from update so methods plug in via thin wrappers.
- Schedule is an explicit experimental variable: state persistence, task reuse, train size, batch size, #epochs, updates per batch, assessment timing.
- Splits vs views: update evidence only from D_train; frozen **update-validation** view (D_val) assessed at epoch end and never fed back; **ID transfer** and **OOD transfer** views from D_test; **replay/retention** view (re-run train tasks) for forgetting.
- Data: Terminal-Bench 2.0 + HLE text-only Math/Physics as source: 80 train / 35 val / 55 ID test; OOD = 80 HLE CS/AI + Engineering tasks. 5 epochs, batch 20, one update per batch. Main backend DeepSeek-V4-Flash; methods ACE, TF-GRPO, AHE. Validation/final views use **single-attempt** evaluation, and each configuration appears to be **one training run** (no seed repeats reported) — so with 35 val tasks one task = ~2.9 pts, 55 ID tasks one task = ~1.8 pts.
- Metrics: Perf, SR; UVG_prev (gain vs previous snapshot), UVG_base (gain vs initial); IDG, OODG (final minus initial); Forgetting FR = max(0, Perf(A0, D_R) − Perf(A_T, D_R)); plus rollout/update tokens, tool calls, wall-clock. Domain-level macro averages. Saves harness diffs, update summaries, snapshots so metrics can be recomputed offline; LLM-judge/manual diagnostics are explicitly secondary to verified outcomes.

### Key numbers
- Main (best-val snapshot; V0→V*, UVG | ID0→ID*, IDG | OOD0→OOD*, OODG | rollout tok/task | update tok/update):
  - AHE: 40.0→57.1 (+17.1) | 40.0→49.1 (+9.1) | 22.5→28.8 (+6.3) | 1.46M | 3.91M
  - ACE: 37.1→40.0 (+2.9) | 30.9→34.5 (+3.6) | 22.5→25.0 (+2.5) | 1.93M | –
  - TF-GRPO: 31.4→48.6 (+17.1) | 30.9→34.5 (+3.6) | 26.3→23.8 (**−2.5**) | 2.33M | 1.60M
  - => Same +17.1 validation gain for AHE and TF-GRPO, but very different held-out transfer. Validation gain alone does not predict ID/OOD.
- Replay/forgetting (AHE, 80 train tasks): initial 34/80 → final 43/80, but **after epoch 4 replay collapsed to 6/80** (evolved message-construction regression in middleware) before recovering. Final vs A0: fixes 13, forgets 4, net +9.
- Batch size (AHE; val and ID initial→final): b10 37.1→22.9 (−14.3), 38.2→23.6 (−14.5), 39/40 updates; **b20 40.0→57.1 (+17.1), 40.0→49.1 (+9.1)**; b40 37.1→40.0 (+2.9), 41.8→43.6 (+1.8); b80 42.9→25.7 (−17.1), 41.8→25.5 (−16.4). Non-monotonic; update cost ~3–4M tokens/update regardless.
- Source diversity: HLE-only final snapshot collapses to **0.0** on val/ID/OOD (IDG −22.0, OODG −21.2), though its epoch-3 snapshot was useful (ID 47.3, +7.3; OOD 25.0, +3.8). Mixed source ends at +9.1 ID / +6.3 OOD.
- Cross-model (ID gain, rows=evolved-with, cols=eval backend DeepSeek/GLM/GPT-5.4): DeepSeek +9.1/+7.3/−3.6; GLM +7.3/+3.6/+0.0; GPT-5.4 −1.8/−7.3/+5.5. OOD: DeepSeek +6.3/+0.0/−8.8; GLM −5.0/+3.8/−5.0; GPT-5.4 +3.8/−1.3/−7.5. GPT-5.4-evolved harness: ID +5.5 but OOD −7.5.
- Main-run budgets: AHE 1053.8M rollout + 78.1M update tokens, 14h06m; ACE 1384.0M rollout; TF-GRPO 2615.1M rollout + 32.0M update.

### Recommended protocol
- Never feed validation/test examples or private verifier artifacts into update evidence; freeze views before scored runs; save task IDs per view.
- Evaluate frozen snapshots at **every** update point, not just initial vs final; intermediate snapshots can be better than final and the trajectory is non-monotonic.
- Report ID and OOD transfer separately; OOD (shifted domain) and cross-backend transfer can flip sign.
- Run a **replay** view on previously solved tasks and report fix vs forget counts (churn), not just net.
- Report cost (rollout + update tokens) alongside gains.
- Treat schedule (batch size, source diversity) as a variable; ablate it.

### Implication for us
- Promotion gate for a mutation = (a) gain on a frozen validation slice the proposer never saw, (b) **no regression on a replay set of previously-passing customer cases** (explicit fix/forget counts per mutation), (c) cost delta. A mutation can fix 13 and break 4; survival should require the broken set to be reviewed by the FDE.
- Version every harness snapshot and keep the ability to roll back to any earlier snapshot — "best" is often an intermediate one (HLE-only epoch 3 vs collapsed final).
- Middleware/runtime-contract mutations are high blast radius (one regression took replay 43→6); gate them harder than prompt-text mutations.
- Evidence diversity matters: a single customer's narrow case stream can drive the harness to a local optimum; batch evidence (~20 traces per proposal was best here) rather than per-failure mutations.
- A harness evolved with one model may hurt another; re-validate on model upgrades.

---

## 3. Evo-Bench: Can Language Models Improve Agent Harness? (arXiv 2608.09096)

- Citation: Lisheng Huang*, Chen Yang*, Hao Zhou, Huatong Song, Zongchao Chen, Ran Le, Yang Song, Wayne Xin Zhao, Tao Zhang. Renmin University of China / BOSS Zhipin (Nanbeige). arXiv:2608.09096v2, 11 Aug 2026.
- URL: https://arxiv.org/abs/2608.09096
- Read: full text incl. appendices (24 pp.).

### Setup
- Benchmarks the **evolver model** (not an algorithm): fixed policy model (DeepSeek-V4-Flash), fixed evolve harness (Claude-Code-like, with research skills: query_rollouts, diff_task, analyze_evals, log_experiment, record_insight, architecture_checkpoint), seed policy harness = minimal CodeAct loop (shell + finish).
- Domains/sources: Search (BrowseComp, HLE), Office (GDPval, APEX-Agents), General (Claw-Eval). **160-task visible validation suite (32/source) vs disjoint 448-task held-out evaluation suite** (128 BC, 128 HLE, 64 GDPval, 64 APEX, 64 Claw). Evolver may only request evaluations on val; final frozen harness scored once on eval.
- Budget: 20 iterations (each formal val eval consumes one), 1,000 evolver steps, 48 h. Policy rollout ≤300 steps / 1 h. Search/Office 1 rollout; Claw-Eval 3 rollouts (Pass^3). LLM judge Qwen3.7-Plus (temp 0). **All experiments run once.**
- **Harness-guided benchmark construction** (key methodological idea):
  1. Auxiliary tasks (disjoint corpora; 320 tasks) → 4 frontier evolvers produce 73 harnesses → content-hash dedupe to 65 unique → k-medoids picks 12 representative harnesses H_aux.
  2. Score 2,329 candidate tasks under all 12 harnesses. **Harness sensitivity Sens(x) = Pearson corr(task score under h, leave-one-task-out mean quality of h)**; difficulty = 1 − mean score. Drop Sens ≤ 0 (APEX 133/421, BC 47/768, Claw 60/157, GDPval 95/215, HLE 62/768 removed), stratify by difficulty, take highest-Sens tasks per stratum, **randomly split within strata** into val/eval so both have matching difficulty and sensitivity (goal: "cross-suite alignment").
  - Mean Sens of selected: APEX 0.377, BC 0.256, Claw 0.386, GDPval 0.368, HLE 0.313.
- Metrics: Overall score on held-out eval; **AnytimeVal** = mean over iterations of best-so-far validation score (early termination carries best forward).
- Integrity controls: evolver writes only policy harness + workbench; policy rollouts get immutable snapshot, answer-stripped task; scanner zeroes trials where benchmark answers reached the policy via web/shell; Codex-based semantic audit of all trajectories caught **MiniMax M3 evading the detector** (scores zeroed, corrected result reported).

### Key numbers
- Baselines (Search/Office/General/Overall): CodeAct seed 11.7/38.4/48.4/**29.7**; human "Artificial harness" (MiroFlow + Stirrup + Claw-Eval) 46.7/43.9/56.3/**47.5**.
- Evolvers (Overall, gain, AnytimeVal): GPT-5.6 Sol 46.3 (+16.6) AV 50.1; Claude Opus 4.8 45.8 (+16.1) AV 51.4; GLM-5.2 43.5 (+13.8) AV 51.0; Qwen3.7-Max 41.5 (+11.8) AV 49.3; MiniMax-M3 41.4 (+11.7) AV 49.0; Qwen3.6-27b 39.4 (+9.7) AV 46.9; DeepSeek V4 Pro 39.1 (+9.4) AV 45.4; Kimi K2.7 Code 38.7 (+9.0) AV 43.4; Gemma-4-31B 35.9 (+6.2) AV 36.2.
- Gains concentrated in Search (+12.5 to +34.8); **Office roughly flat (−0.6 to +3.3)**; General 0 to +11.0. Best evolved harness still < human harness overall (46.3 vs 47.5).
- Note AnytimeVal (validation best-so-far) is consistently several points above held-out Overall (e.g., Opus 51.4 vs 45.8; GLM 51.0 vs 43.5) — a val→held-out gap, though val and eval sets differ in size/composition so not a clean overfitting measure.
- **Noise floor observed: 2.2-point Overall-score range across byte-identical harness revisions** (Qwen3.6-27B I8/I10/I12, validation, 160 tasks).
- Selection failures (validation best → frozen): Qwen3.6-27B 49.7 (I10) → 45.4 (I18); DeepSeek-V4-Pro 46.5 (I3) → 42.6 (I15), labeled I3 an "outlier" without re-evaluating; Kimi 45.9 (I13) → 45.9 (restored byte-identical best). Only 1 of 3 analyzed evolvers froze its best revision.
- Catastrophes: Qwen bundled edits → malformed verifier crashed 159/160 tasks (score 0.3) missed by local preflight; Kimi's I1 architecture scored 2.1.
- Budget: most evolvers stopped early (e.g., 15/20 iters, ~200 steps); GPT-5.6 Sol used 20 iters, cost >$500/run; GLM-5.2 & Qwen3.7-Max < $40; DeepSeek-V4-Pro < $1. Larger budget (24h→36h→48h) monotonically improved Overall and AnytimeVal for Qwen3.7-Max and GLM-5.2.
- Cross-policy: harnesses lift other policy models over their own CodeAct baseline (Qwen3.6-35B-A3B 13.9 → 27.9/29.2; GLM-5.2 policy 38.0 → 42.7/48.4). Note: these are re-runs of evolution with the new policy, not transfer of a frozen harness.

### Recommended protocol
- Build eval sets from **harness-sensitive** tasks (tasks whose score correlates with harness quality across a diverse harness pool) and stratify val/eval by difficulty and sensitivity so validation gains predict held-out gains.
- Visible validation vs disjoint held-out evaluation; held-out scored only after freeze and never returned to evolver.
- Report both final held-out score and an anytime/progress metric.
- Integrity: sandbox separation, answer-leak scanning, and semantic audit of trajectories for reward hacking.
- Failure-mode lessons (App. D.4): "paired failure analysis, one falsifiable mechanism per iteration, cheap preflight checks, automatic best-revision recovery, and an architectural-reset trigger after repeated local failures"; replicate before calling a regression noise.
- Caveat: single run per config, no CIs — their own leaderboard gaps of ~0.5 pts (GPT-5.6 vs Opus 4.8) are well inside the 2.2-pt identical-harness range.

### Implication for us
- **Measure our noise floor directly**: re-run the byte-identical harness version N times on the customer eval set; any mutation delta below that range is not evidence. Use content hashes for versions so identical re-runs are detectable.
- **One mutation = one falsifiable hypothesis**; don't bundle. Require a smoke/preflight run before a full eval (catch the "crash 159/160" class).
- **Auto-keep the best-validated version** and make rollback automatic; don't let the proposer (or FDE under time pressure) freeze the latest.
- Curate the customer eval set for harness sensitivity: drop cases that fail/pass regardless of harness (they add noise, not signal).
- Expect domain unevenness: office-style workflows specific to a customer are exactly where auto-evolution underperformed humans — the FDE's edit is likely most valuable there; track survival by mutation domain/type.
- Leakage: proposer must never see held-out cases or expected answers; audit mutations for embedded answers/customer-case literals.

---

## 4. HarnessOpt-Bench: Evaluating LLMs at Harness Optimization (arXiv 2608.06301)

- Citation: Varun Ursekar, Apaar Shanker, Yash Maurya, Shehab Yasser, Vijay S. Kalmath, Veronica Chatrath, Yuan (Emily) Xue. Scale AI. arXiv:2608.06301v1, 6 Aug 2026. Builds on VeRO (Ursekar et al., ICML 2026).
- URL: https://arxiv.org/abs/2608.06301
- Read: full text incl. appendices (27 pp.).

### Setup
- Optimizer = LLM + coding harness; gets pinned seed harness H0, graded feedback, fixed target-eval budget; edits harness (any file, fixed invariants θ = model, environment, verifier) and **nominates** a final candidate H+. Score = **normalized gain g = (E(H+) − E(H0)) / (1 − E(H0))** on a held-out test partition never visible during search.
- **Graded disclosure**: dev split reveals case inputs, per-case outcomes, traces (for diagnosis); val split reveals **only aggregate score** (for selection); test reveals nothing, evaluated by a trusted server only after nomination.
- Trusted execution environment: optimizer sandbox can write only target harness; per-case ephemeral sandboxes; model API gateway with allow-lists and per-scope token budgets; every candidate versioned for audit.
- Budget: caps on eval calls per partition (Section 3 says 100; Section 5.3 says 200 — internal inconsistency) and **four full case passes** each on dev and val, plus target-model token cap. Optimizer's own inference metered but uncapped.
- Tasks (dev/val/test; target model; seed baseline ± SE over K=3): OfficeQA 49/98/99, deepseek-v4-flash, 0.341±0.023; BrowseComp-Plus 33/66/66, deepseek-v4-flash, 0.462±0.020; Terminal-Bench 2.0 17/36/36, grok-build, 0.241±0.009; GAIA 33/66/66, gpt-5.4-mini, 0.000 (non-functional stub).
- Seed baseline measured as mean over **K=3 independent rounds**; nominated candidate scored 3× per test case and averaged; **each optimizer configuration run twice**. Timeouts = 0.
- Grid: 5 optimizer models (claude-opus-5, claude-sonnet-5, gpt-5.6-sol, gpt-5.6-terra, kimi-k3) × {shared opencode, native harness} × 4 tasks; +goose and mini-swe-agent on GAIA; 111 scored runs.

### Noise handling ("resolution band")
- Estimate evaluation noise by **scoring the same candidate twice on the same cases**, take the median discrepancy, and carry it to the K=3 normalized-gain scale. Differences smaller than the band are "unresolved" (descriptive threshold, not a significance test).
- Bands (normalized gain): OfficeQA ±0.045, BrowseComp-Plus ±0.066, Terminal-Bench ±0.054, GAIA ±0.035. LSS-λ model-effect resolution ±0.058 (split-round swing).
- Report ranges across replicate runs explicitly and say "two rounds do not estimate dispersion"; rank in **tiers**, not a full ordering.
- Model effect estimated via additive decomposition ḡ_mt = μ + τ_t + λ_m + ε (LSS-λ); cross-checked with within-task standardized gain and mean rank (identical ordering).

### Key numbers
- Best configs capture ~2/3 of OfficeQA headroom (opus-5+opencode 0.63) and ~1/2 of BrowseComp-Plus (0.48); weakest unresolved from zero on BC-Plus and TB (gpt-5.6-terra: −0.03 to 0.04).
- Changing optimizer model moves gain by **0.142** on average vs **0.079** for changing coding harness (~1.8×). Shared vs native: shared wins 11/20 pairs, native 9/20; 11 pairs exceed band but direction varies.
- LSS-λ: opus-5 +0.228 (tier 1); sonnet-5 +0.029, kimi-k3 −0.014, gpt-5.6-sol −0.069 (tier 2); gpt-5.6-terra −0.174 (tier 3).
- Release ladder (OfficeQA): GPT releases +0.03 → +0.49 monotonic (3 of 4 steps exceed band); Opus releases +0.37 to +0.59, non-monotonic.
- Search process: fraction of 8 pre-registered levers touched correlates with gain (Spearman ρ +0.34 to +0.88); shipped edit breadth ρ +0.33 to +0.96; lines changed ρ +0.44 to +0.95. **Share of actions reading eval output is negatively associated with gain (−0.31 to −0.64)**; detailed traces requested only 16 times by 7 of 111 cells. One config touched 3/4 of levers, made 7 edits, and shipped the unmodified seed; 7 table entries shipped the seed on ≥1 round.
- Budget binding: median optimizer uses 8 eval calls (4%) but **82% of case allowance**; 55/100 cells exhaust at least one partition's case budget.
- **Visible validation is optimistic**: most runs' submitted-candidate test score < best validation score seen during search (cannot separate selection-induced overfitting from val-test mismatch).
- Off-the-shelf harnesses often beat seeds by a lot (e.g., OfficeQA seed 0.341 vs openhands-sdk/mini-swe-agent ~0.71–0.73; TB seed 0.241 vs opencode 0.607) — a strong "just swap in a stock harness" baseline.

### Recommended protocol
- Fixed invariants (model, env, verifier); disjoint dev/val/test with **graded disclosure** (traces on dev, aggregate only on val, nothing on test).
- Enforce boundaries in infrastructure (not instructions): held-out data, credentials, budgets absent from optimizer sandbox.
- Budget denominated in eval calls and **case-runs** (not optimizer compute) for fairness; report token cost as first-class.
- Normalize gain by headroom; measure a per-task resolution band by re-scoring identical candidates; treat sub-band differences as ties; K=3 rounds per score; ≥2 replicate optimizer runs; report ranges.
- Compare against seed AND off-the-shelf harness baselines.
- Limitations they flag: fixed dev/val feedback can still reward evaluator-specific strategies — recommend per-run **jitter** in cases, tool behavior, and verifier implementation.
- Note: no random-search / matched-budget random-mutation baseline is included.

### Implication for us
- Adopt the **resolution band** directly: for each customer eval set, re-score the current version twice (or K=3) and compute the median discrepancy; a mutation is "resolved-better" only if its delta exceeds the band. Record band per customer in the version metadata.
- Adopt **graded disclosure** for the proposer: it may see traces for a diagnostic split, only an aggregate on the selection split, and never the promotion/held-out split. The FDE-facing promotion score should come from the hidden split.
- Always show a "stock harness" and "unchanged seed" baseline next to a mutation's score.
- Log whether a mutation is effectively a no-op (shipped seed) — survival of a no-op is meaningless.
- Budget the proposer in case-runs; case passes, not call counts, are what bind.
- Don't equate "agent read the traces carefully" with quality; judge on held-out outcomes.

---

## 5. Towards Direct Evaluation of Harness Optimizers via Priority Ranking (arXiv 2605.22505)

- Citation: Kai Tzu-iunn Ong*, Minseok Kang*, Dongwook Choi*, Junhee Cho, Seungju Kim, Seungwon Lim, Geunha Jang, Minwoo Oh, Bogyung Jeong, Sunghwan Kim, Taeyoon Kwon, Jinyoung Yeo. Yonsei / MSRA / Texas A&M. arXiv:2605.22505v1, 21 May 2026.
- URL: https://arxiv.org/abs/2605.22505 (code/data: github.com/k59118/Harness_Optimizer_Evaluation)
- Read: full text incl. appendices (50 pp. PDF; figures partially extractable).

### Setup
- Argues end-improvement (final agent SR) is an indirect, expensive way to evaluate optimizers and hides step-level mistakes. Proposes **priority ranking**: given optimization history H_t (harnesses, trajectories, scores, summaries), the optimizer ranks harness components {prompt, tool, memory, workflow} by expected impact if updated next. Scored vs labels by Acc@1, NDCG (also MRR, Kendall τ in appendix).
- **SHOR dataset**: 595 candidate harnesses from Meta-Harness runs (gpt-4.1-mini target, 4–12 val instances/iter, 20 iters) → for each, 3 coding-agent annotators (Codex GPT-5.3-Codex, Claude Code Sonnet 4.6, Gemini-CLI Gemini-3-Pro) each produce a component-targeted next harness per component; run target agent (Qwen-3.5-Flash, **single rollout on 20 instances**) to get ΔSR per component → per-annotator ranking → keep only if **Kendall's W > 0.5** (238/595 kept) → consensus by mean ΔSR → drop if any adjacent gap ≤ δ = 0.005 (182/238 kept) → human verification. Avg W = 0.7192. Flawed-harness subset SHOR-Flaw (text says 108 of 182 flawed; stats table says 122 — internal inconsistency).
- Domains: GAIA, Spider 2.0-lite, SWE-bench Verified, τ2-Bench; OOD: AppWorld, GPQA.

### Key numbers
- **Analysis I**: in 15 real ReCreate-style optimization trajectories (150 harnesses; 3 optimizers GPT-5.2 / Sonnet 4.6 / Qwen3.6-Plus; target gpt-5-mini + mini-swe-agent; 10 iters, 4 random val tasks per iter, 40-instance held-out test), humans judged **44.8–48.2% of optimization steps erroneous** (harmful).
- **Analysis II**: errors persist — apart from prompt errors (17.8% don't persist), **94.4% of errors in other components remain in the final harness**.
- **Analysis III**: optimizers predicting whether their own update helps (binary) — avg accuracy GPT-5.2 0.549, Sonnet 4.6 0.334, Qwen3.6-Plus 0.503 (**≈ chance or worse**). Only 10 harness pairs per domain — small sample.
- Error taxonomy (8 types): Redundant Duplication, **Hardcoding** (e.g., τ2 "refill exactly 2GB"), **Task-specific Addition**, Hallucination (references nonexistent tool), Overengineering, Direct Performance-degrading Update, Overgeneralized Heuristic, **Safety Violation** (e.g., removing step/cost limits).
- Priority-ranking results (avg over 4 domains): Acc@1 range 0.216–0.305 (best OpenHands-CLI + DeepSeek-V4-Pro 0.305); NDCG 0.768–0.793 (best Claude Code + Sonnet 4.6 0.793). With 4 components, random Acc@1 = 0.25, so most optimizers are near chance on top-1. Domain rankings inconsistent. GPT-5.2 in OpenHands-CLI beats GPT-5.2 in Codex in 3/4 domains (+9.3 pp Spider, +8.9 pp SWE-V).
- **Correlation with real optimization gain** (10-iteration optimization from 5 base harnesses/domain, 4 val instances, 45-instance held-out test, 5-run average): Acc@1 vs ΔSR average Pearson **ρ = 0.602 (p = 0.038)**; per domain GAIA 0.649 (p 0.022), Spider −0.093 (p 0.774), SWE-V 0.632 (p 0.027), τ2 0.341 (p 0.278); OOD average 0.518 (p 0.085), AppWorld 0.600 (p 0.039), GPQA 0.282 (p 0.375). NDCG average 0.653 (p 0.021). (n ≈ 12 optimizer configs; not all per-domain correlations significant.)
- Correlation strongest for mid-stage harnesses (T in [6,10]: 0.469; then 0.458, 0.354, late 0.087).
- Cost: end-SR observation $524.3 / 1089.8 min vs priority ranking $63.7 / 63.2 min (**~8× cheaper, ~17× faster**).
- Fixing flawed harnesses (human-judged resolve rate, 25 flawed harnesses/domain): without flaw location avg 0.050 (Gemini-CLI), 0.110 (Claude Code), 0.180 (Codex); **with the flawed component given: 0.560, 0.450, 0.350** (+17 to +51 pp). Bottleneck is locating the problem, not fixing it.

### Recommended protocol
- Evaluate optimizers **directly at the step level**, not only by end improvement; audit intermediate updates for the 8 error types; check whether errors persist to the final harness.
- Use priority ranking as a cheap screen / **CI quality gate** for updates (a "necessary, not sufficient" condition).
- Build labels via counterfactual component-targeted variants + rollouts, keep only high inter-annotator agreement (Kendall's W) and clear performance gaps, then human-verify.
- Caveats for us: labels rest on single-rollout 20-instance SR deltas and δ = 0.005 (below one-task granularity), val sets of 4 instances in the optimization runs — noise is not explicitly characterized; correlation n is small.

### Implication for us
- Expect roughly **half of proposed mutations to be harmful** and the proposer to be unable to tell which (self-prediction ≈ chance). This is the strongest argument for the human FDE gate and for **not** using proposer confidence as a promotion signal.
- Build a **mutation lint/audit** against the 8-error taxonomy (hardcoded customer literals, task-specific rules, duplicate tools, references to nonexistent tools, removed limits/safety rails, unpruned append-only growth). Safety-violation mutations (removing step/cost limits) should be auto-blocked.
- Track **error persistence**: accepted mutations that later get reverted/edited = errors that survived; survival must be measured over time, not just at accept.
- A **priority/localization step** before mutation ("which component is the bottleneck?") can be a cheap pre-screen and increases fix rates a lot when the location is right; FDEs could label the component, giving us ranking data (SHOR-style) from our own logs.
- FDE edit/reject decisions per component are a natural source of step-level labels for evaluating the proposer directly, cheaper than full rollouts.

---

## Cross-paper synthesis: evaluation protocol for mutation proposals and promotion

Convergent evidence (with HarnessDev's ±4.75-pt noise / 53% agreement):
- Noise floors are large relative to typical gains: 2.2 pts across byte-identical harnesses (Evo-Bench, 160 tasks); resolution bands ±0.035–0.066 normalized gain (HarnessOpt-Bench); held-out gains of +0.6 (Rethinking) sit inside that.
- Visible/validation scores are optimistic vs held-out (HarnessOpt-Bench Fig. 13; Evo-Bench AnytimeVal > Overall; SEAGym same val gain → different ID/OOD).
- Self-selection of the final version is unreliable: 2 of 3 Evo-Bench evolvers froze a worse-than-best revision; SEAGym's HLE-only run's final snapshot collapsed to 0 after a good epoch-3 snapshot; optimizers predict their own update's sign at ≈ chance (priority ranking paper).
- About half of individual updates are harmful and most harmful non-prompt updates persist (priority ranking paper); updates often memorize task specifics (Rethinking; hardcoding/task-specific addition in taxonomy).
- Matched-budget test-time scaling (best-of-K, sequential refinement) matches or beats harness evolution on the same tasks (Rethinking).
- None of the five papers runs a **matched-budget random-mutation / random-search baseline**; Rethinking's parallel sampling/sequential refinement and HarnessOpt-Bench's off-the-shelf harnesses are the closest analogues. This is a gap we can fill.

Proposed protocol for our system:
1. **Splits per customer**: diagnostic split (proposer sees traces), selection split (proposer sees aggregate only), promotion/held-out split (never exposed; used for the FDE-facing score), plus a **replay set** of previously passing cases. Freeze split membership and record IDs in each version.
2. **Noise floor**: re-run the current version K≥3 times on the promotion split; compute resolution band (median re-score discrepancy, HarnessOpt-Bench style) and store it. A mutation is "resolved-better" only if its delta exceeds the band; otherwise label "unresolved" (not "improved").
3. **Baselines for every proposal at matched case-run budget**: (a) unchanged version re-run (noise), (b) best-of-K / retry with unchanged version (test-time-scaling counterfactual), (c) random/naive mutation of the same component type (our addition), (d) stock harness where available.
4. **Per-mutation report**: delta ± band on promotion split; fix/forget counts on replay set; cost delta (tokens, latency); ID vs OOD (e.g., other customers' or other task types) where available.
5. **Pre-screen / lint**: one hypothesis per mutation; smoke test; audit for hardcoded case literals, task-specific rules, duplicated/nonexistent tools, removed limits; auto-block safety violations.
6. **Promotion & rollback**: keep all snapshots content-hashed; the system auto-tracks the best-on-selection version; promotion decided on held-out split + FDE; automatic rollback on replay regressions; re-validate on model upgrade (cross-backend transfer is unreliable).
7. **Survival metric design**: survival counted only for resolved-better, non-no-op mutations; measure survival at multiple horizons (accept → still present after N subsequent versions / N weeks); record FDE edits per component as step-level labels (priority-ranking style) to evaluate the proposer directly.
