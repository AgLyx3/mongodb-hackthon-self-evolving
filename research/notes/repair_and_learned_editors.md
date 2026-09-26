# Repair & Learned Harness Editors — reading notes

Project context: self-evolving FDE deployment harnesses — agent proposes versioned harness mutations; human FDE accepts / edits / rejects; goal is a mutation policy that improves from the FDE correction history.

Method: all four PDFs downloaded from arxiv.org/pdf/<id> and full text extracted with pypdf (/tmp/rp/*.txt). Numbers below are copied from the extracted text; anything not verified is flagged.

---

## 1. HarnessFix

**Citation:** Mengzhuo Chen, Junjie Wang, Zhe Liu, Yawen Wang, Haiming Zheng, Qing Wang. "From Failed Trajectories to Reliable LLM Agents: Diagnosing and Repairing Harness Flaws." arXiv:2606.06324 (v2, 2 Jul 2026), cs.SE. https://arxiv.org/abs/2606.06324 . Code: https://github.com/HarnessFix/HarnessFix . (ISCAS / UCAS / Tianjin U.)

**Core mechanism.** Four LLM agents (no training): (1) trace-abstraction agent builds a *Harness-aware Trace Intermediate Representation (HTIR)*; (2) diagnosis agent attributes failures and consolidates them into *flaw records*; (3) repair agent maps flaw records to *scoped repair operators* and writes a *repair specification*, then a patch; (4) validation agent does scope/static checks + held-out regression-aware acceptance. Outcomes are stored as *harness repair memory*.

- Uses ETCLOVG 7-layer taxonomy (Execution, Tooling, Context/Memory, Lifecycle, Observability, Verification, Governance).
- Motivational study: 30 OSS agent repos, ~57,780 dev records (issues/PRs/commits/releases); 26,174 (~45.3%) harness-related. Flaws in all 7 layers; Lifecycle, Tooling, Observability most frequent (29/30 repos). Repair operators (Table II) mined from developer fixes, e.g. Tooling: schema narrowing, argument validation, error-message repair; Lifecycle: loop guarding, retry/timeout bounding, verification-gated finalization; Verification: expected/actual state comparison, effect-evidence completion guarding; Governance: high-impact action approval gating, etc.

**Diagnosis / localization.**
- HTIR: each *TraceStep* = request/response + derived annotations (role, execution status, artifact/state effect — e.g. "success but no observable external effect").
- *Data-flow links* (source span → target span, copied/summarized/semantically reused) and *control-flow links* (continue/retry/delegate/validate/finalize/terminate + triggering condition).
- *Implementation anchors*: map runtime evidence to editable artifacts (file + line range, prompt id, tool-schema id, workflow node, validator id) with anchor relation + evidence.
- Per-step layer mapping (trace-specific, not file-level).
- Diagnosis in 4 steps: symptom localization -> evidence backtracking along links (ranked candidate steps) -> candidate adjudication (did step form/propagate/fail to expose/constrain/validate?) -> layer assignment. Output: diagnosis record (responsible steps + root cause, failure signal, harness diagnosis).
- *Flaw consolidation*: single failures may be accidental; merge diagnosis records with overlapping layers & same root cause into recurring flaw records before editing anything.

**Validation of edits.** Repair spec = target & scope (flaw, layers, primary + auxiliary operators), edit constraints (allowed artifacts, *forbidden artifacts* e.g. task data/oracles, test labels, public APIs), required behavior. Pre-validation: diff conforms to spec + syntax/static checks. Then held-out validation set: accept only if target improvement achieved AND regressions on previously-solved tasks within limit.

**Learned policy?** No weight training. "Learning" = harness repair memory: each record stores flaw, layers, spec, diff summary, pre-validation + validation results, regressed tasks, and NL description of conditions where repair applies / doesn't. Accepted records = exemplars for similar future flaws; rejected records labeled by cause (pre-validation failure / insufficient improvement / excessive regression) to avoid re-proposing. This is essentially an accept/reject log used in-context.

**Key results (GPT-5 mini default; means of 3 runs; splits train/val/test: GAIA 60/30/60, SWE-Bench Verified 100/50/100, AppWorld 90/45/90, Terminal-Bench 2.0 Verified 34/17/34).**
- Over H0: +6.3 to +18.4 pts; avg +11.1. GPT-5 mini: GAIA 43.3->61.7 (+18.4), SWE 45.3->57.3 (+12.0), AppWorld 36.7->43.0 (+6.3), TB2 17.6->26.5 (+8.9). Across 5 LLMs (GPT-5 mini, Claude Sonnet 4.5, DeepSeek V3.2, Qwen3.5 Plus, Gemini 3 Pro), per-LLM avg gain 10.3-12.5.
- vs baselines (GPT-5 mini): beats human-designed harnesses by 6.3 avg (1.9-10.0); beats GEPA/SCOPE/ReCreate/Meta-Harness by 6.9 avg (2.6-16.7). Vs Meta-Harness: +2.6 to +5.0 pts while Meta-Harness uses 63.5%-100.5% more tokens (e.g., GAIA 94.2M vs 57.6M tokens). Sign tests p = 2.4e-4 to 4.9e-4.
- Diagnosis accuracy vs 3-annotator gold (20 failed traces/benchmark), Table V (Step/Cause/Anchor/Layer-F1/Operator): Raw trace 55.0/53.8/50.0/58.4/51.3; +data-flow 70.0/68.8/65.0/73.2/66.3; +data/control 77.5/75.0/72.5/79.4/73.8; Full HTIR 85.0/83.8/81.3/86.2/82.5. Prior step-attribution methods cited at ~45-52%.
- Ablations (GAIA/SWE/AppWorld/TB2): full 61.7/57.3/43.0/26.5; prompt-only 50.6/48.3/37.4/18.6; w/o trace diagnosis 51.1/50.7/38.1/21.6; w/o scoped operators 50.6/49.3/37.4/18.6; w/o regression-aware acceptance 55.6/53.3/39.3/24.5.
- Cross-model transfer of GAIA harness repaired with GPT-5 mini: +5.5 (Claude Sonnet 4.5), +7.8 (DeepSeek), +9.5 (Qwen), +8.9 (Gemini).
- Layers touched: HarnessFix 4-7 layers per benchmark; GEPA/SCOPE 1, ReCreate 2, Meta-Harness 7 (but untargeted).

**Implications.**
- (a) Diagnosis: Strongest evidence that structured diagnosis pays: raw-trace -> HTIR lifts step accuracy 55 -> 85. For FDE: build a trace IR with implementation anchors into the *customer harness artifacts* (prompt files, tool schemas, configs), and present the FDE with the diagnosis record + anchor, not just a diff. Flaw consolidation across multiple failures before proposing = natural noise filter. The operator taxonomy (Table II) is a ready-made mutation action space / label set for FDE edits.
- (b) Learning from FDE accept/edit/reject: HarnessFix's repair memory is a direct template: store (flaw record, operator, spec, diff, outcome, reject reason, applicability conditions). Replace/augment the automated validation verdict with the FDE verdict; FDE *edits* give the "correct operator/scope" label. Operator-accuracy metric (82.5%) suggests a supervised target: predict operator & anchor that FDE ultimately accepts. Forbidden-artifact lists = encode FDE-rejected scopes as constraints.
- (c) Sparse/unreliable feedback: consolidation (don't act on one failure), held-out validation with regression budget, and explicit rejection causes. Removing regression-aware acceptance costs 2-6 pts — gating matters even with a good diagnoser.

---

## 2. Harness-R1

**Citation:** Shuai Shao, Kangning Zhang, Qingyao Li, Shijian Wang, Hao Wang, Wenxiang Jiao, Yuan Lu, Yi Guo, Weiwen Liu, Weinan Zhang. "Harness-R1: Learning to Edit Executable Runtime Harnesses from Agent Failure Trajectories." arXiv:2608.02276 (v1, 3 Aug 2026), cs.AI. https://arxiv.org/abs/2608.02276 . Code: https://github.com/DeepExperience/Harness-R1 ; models: https://huggingface.co/ShaoShuai0605/Harness-R1 . (SJTU / Xiaohongshu / Southeast U.)

**Core mechanism.** Post-train a *dedicated 9B "harness engineer"* (Qwen3.5-9B) with cold-start SFT + online GRPO; the target agent (frozen Qwen3.5-9B) is never updated. Engineer reads a batch "failure packet" once and emits one executable overlay patch; patched target reruns the same batch; batch reward delta trains only the engineer. Claims to be first to make failure-conditioned, lifecycle-wide executable-harness editing a *learned* capability (argues Meta-Harness, AHE, AutoHarness, HarnessFix, etc. keep proposer fixed).

- Action space: JSON patch of `add_code_hook` actions at 4 lifecycle hooks: `on_init` (skills/tool hint), `make_pre_hint` (state-conditioned message), `on_before_action` (block_and_prompt / rewrite_action / force_action — a runtime guardrail), `on_post_step` (inject_hint / force_action recovery). Hooks are Python `hook(ctx, nb)` with no imports/global state; host runtime interprets returned structured effects. Benchmark-specific runtime context exposes predicates (e.g., `product_price_over_budget`, `repeated SQL`, `premature/empty commit`). Rules: no task-specific answers/IDs.

**Diagnosis / localization.** Minimal and implicit: a *deterministic extractor* keeps only failed episodes and compacts task constraints, selected action–observation excerpts, outcomes, env state into a failure packet. Engineer does "concise recurring-failure reasoning" in a <think> block then outputs patch. No explicit step attribution; localization = choice of lifecycle hook + predicate.

**Validation of edits.** Patch parsed & validated before install; invalid / no-op (behaviorally inert) / incomplete -> reward 0 (treated as no intervention). Valid patch reward = full-batch mean reward change ΔB(P) = (1/n)Σ(R^P_i − R^0_i) over *all* tasks in the batch, including originally-successful ones, so regressions give negative reward. Same-batch, transductive; no persistent patch memory across batches. Authors list as limitation: should add held-out reward against regressions and efficiency terms.

**Learned policy — yes (the core contribution).**
- Cold-start SFT: GPT-5.5 teacher proposes patches from failure packets; keep at most one per packet that is executable, completes rerun, and has *non-negative* reward change -> 877 examples (381 WebShop / 248 ALFWorld / 248 DBBench); full-param, 2 epochs, LR 1e-5.
- Online GRPO: K=8 candidate patches per packet, each independently installed and rerun; advantage = group-normalized reward; clip 0.20/0.28; no KL, no entropy, no format bonus; LR 1e-6; ~1,500 failure packets from disjoint split; 8xH800.
- Signal: realized task-outcome delta of the patch (WebShop shaped reward; ALFWorld/DBBench binary success).

**Key results.**
- Vanilla Qwen3.5-9B target, avg success (WebShop Succ / ALFWorld All / DBBench Succ): 44.3 -> 53.6 (+9.3). Per benchmark: ALFWorld 40.6 -> 53.2; WebShop 31.2 -> 42.2 (score 66.0 -> 69.9); DBBench 61.0 -> 65.3.
- Supervised-only engineer: 46.4 avg (Harness-R1 is +7.1 over it — RL on outcomes is what matters).
- Frontier models prompted as editors: GLM-5.2 48.8 (best), GPT-5.5 47.9, DeepSeek-V4-Pro 45.9, Qwen3.5-397B 45.8, Kimi-K2.6 45.3, Gemini-3.5-Flash 44.3. Self-Refine 41.8 (hurts), ReAct 47.5; Reflection 55.8 but under success@2 (not comparable).
- Co-evolution: after direct target-agent SFT (2,515 successful trajectories) avg 59.2 -> 64.2 (+5.0) with a target-specific engineer.
- Transfer of the *editing policy* to 20 unseen target models (Llama/Gemma/Qwen, 1B-72B): mean +7.06 pts; 56/63 target-benchmark combos improve, 4 unchanged, 3 small regressions (≤2.0).
- Sparse-evidence held-out generalization: each engineer sees the same 10 failures, writes one patch, applied to 1,270 held-out tasks, 3 seeds: Harness-R1 +8.9±1.5 (9/9 valid patches); Qwen3.5-397B −4.3±2.5 (8/9 valid); DeepSeek-V4-Pro −0.4±3.6 (6/9 valid).
- Lifecycle ablation (fixed patches): full 53.1 vs no intervention 44.2; w/o pre-action −3.9; w/o post-feedback −3.3; w/o episode init −0.9; w/o pre-decision −0.6. Pre-action dominates WebShop (41.6 -> 31.5 without it), post-feedback dominates ALFWorld (52.1 -> 41.9).
- Fig. 1 (matched-baseline reward change avg): Self-Refine −3.3, Kimi K2.6 +0.1, DeepSeek V4 +1.0, Qwen 397B +1.1, GLM 5.2 +3.7, Harness-R1 +7.0.
- Case studies: WebShop batch 2/10 -> 5/10 successes (narrow Buy-Now guard); ALFWorld 1/10 -> 6/10 (rescued 6, regressed 1); DBBench 4/10 -> 6/10.

**Implications.**
- (a) Diagnosis: Harness-R1 shows you can skip explicit attribution if you have a *narrow, typed action space* (4 hooks + host-defined effect types + exposed predicates) and a strong outcome signal. For FDE harnesses, a typed hook/effect vocabulary makes proposals reviewable and diff-able, and lets the FDE's correction be expressed as "wrong hook / wrong predicate / wrong effect".
- (b) Learning from FDE accept/edit/reject: The two-stage recipe maps directly: (1) SFT on *accepted* (and FDE-edited-final) patches = their teacher-filtered "non-negative" set; (2) preference/RL where reward = FDE verdict (+ rerun delta where available). With K candidates per failure packet and FDE ranking/choosing one, GRPO-style group-normalized advantages or DPO on (accepted, rejected) pairs are natural. FDE *edits* are richer than binary reward: (proposal -> edited) gives a preference pair plus an SFT target. Key finding to cite: supervised-only (46.4) << outcome-RL (53.6); fixed frontier editors are unreliable, so learning from verdicts is worth it. Caveat: they needed ~1,500 packets x 8 candidates x full reruns — FDE-scale data is orders of magnitude smaller, so expect in-context / retrieval / small-preference-model learning first, weight updates later (possibly per-customer "target-specific engineer" as in their co-evolution result).
- (c) Sparse/unreliable feedback: 10-failure experiment is directly relevant — a trained editor generalizes from 10 failures (+8.9) while big prompted editors regress. Invalid/no-op = 0 reward prevents reward hacking via inert patches. Same-batch reward is transductive (acknowledged limitation) -> for FDE, pair human verdict with held-out regression replay.

---

## 3. DemoEvolve

**Citation:** Lirong Che, Yuzhe Yang, Peiwen Lin, Chuang Wang, Xueqian Wang, Jian Su. "DemoEvolve: Overcoming Sparse Feedback in Agentic Harness Evolution with Demonstrations." arXiv:2605.24539 (v1, 23 May 2026), cs.AI. https://arxiv.org/abs/2605.24539 . (Tsinghua / AgiBot.) No code URL seen in the extracted text.

**Core mechanism.** Meta-Harness-style outer loop: a coding proposer (Claude Opus 4.7 Max) inspects a filesystem archive D_t (prior harness code, dev scores, rollout trajectories, raw execution traces — accessed via file ops, not summaries) and writes new candidate harnesses around a frozen task model (GPT-5.4-low for Balatro). The *only* thing varied is proposer-visible information: I_meta = D_t (Meta-Harness); I_open = D_t + external text (rules/tutorials/strategy guides via web search = "OpenResearch"); I_demo = D_t + competent *human trajectories* in the same observation-action format (DemoEvolve). Demonstrations are used as diagnostic references for the proposer, NOT as SFT labels or finetuning data.

**Diagnosis / localization.** Proposer compares failed agent rollouts against human state-action evidence to localize missing state abstractions, poor action priorities, weak resource management, missing tools. Frames problem as *program-level diagnostic credit assignment*: terminal reward gives no update target for a specific harness edit. Distinguishes *score improvements* from *functional harness improvements* (edit must change the model-facing interface or execution behavior in an auditable way).
- 5x3 localization study (same BalatroLLM rollouts; 5 proposer replicates per arm; edits classified Persistent / Phase-gated / State-computed / Tool), Comp. rate = (State+Tool)/total: None 46.2% (10+2 of 26), Human notes 21.7% (1+4 of 23), Human trajectories 45.5% (6+4 of 22). Interpretation: rollouts localize *where it broke* (negative-only evidence); notes give principles but become generic reminders; human trajectories give *positive state-action counterfactuals* specifying *when* an intervention should fire (e.g., `round1_dig_hint` gated on hands_played=0, discards_left≥2, early ante).

**Validation of edits.** Candidate selection on dev seeds only (Balatro seeds A/B/C, 1 rollout per seed per candidate during search; 10 iterations x ~2 candidates = ~60 dev rollouts); selected candidate re-evaluated from scratch on A–E with 3 rollouts/seed; D/E held out. Key addition: a **functional / rendered-context audit** — replay with extra logging to check hooks trigger, derived state vars are computed/injected, model-call inputs change. The Meta-Harness-selected candidate (`face_exposure_shop_hook`) had a non-empty diff but 0 occurrences of its hook strings across 517 inspected model requests (implementation error) — its dev gain was noise. Recommendation: "source-level diffs are insufficient"; audit at rendered-context/execution level.

**Learned policy?** No weight learning. Proposer is a fixed frontier coding agent; "learning" is via the growing archive plus demonstrations in context.

**Key results.**
- Liar's Dice (TextArena; positive control, short-horizon/attributable): task-balanced macro held-out reward 0.392 -> 0.800 (+0.408); Small3 0.400 -> 0.828; OneCall-Wild1 0.383 -> 0.772; all 6 target/opponent cells improve on 30 paired held-out seeds. Dev eval used only N=5 (sometimes 10) seeds per candidate. Evolved harnesses add parsing, legal-action guards, probability/EV computation; weak model -> near-symbolic threshold policy.
- Balatro (capped mean final round, completion): BalatroLLM ID 17.00 (3/9), OOD 16.83 (2/6), overall 16.93 (5/15); Meta-Harness ID 19.33 (4/9), OOD 16.33 (2/6), overall 18.13 (6/15); OpenResearch 16.67 (2/9) / 17.00 (2/6) / 16.80 (4/15); **DemoEvolve 23.33 (8/9) / 20.00 (4/6) / 22.00 (12/15)**. Only 9 human trajectories (3 per dev seed) used.
- Economy behavior (attrition-adjusted shop-entry money): human-curve distance BalatroLLM 32.10, Meta-Harness 30.83, OpenResearch 24.03, DemoEvolve 12.26; late-game distance 55.25 / 54.89 / 48.36 / 6.49; late reach 0.39 / 0.45 / 0.32 / 0.81.
- Cost: ~$2.13/rollout; ~$160 per evolution run in task rollouts (excl. proposer).
- Caveat: very small samples (3 rollouts x 5 seeds, single game); authors acknowledge limited task coverage.

**Implications.**
- (a) Diagnosis: Failure traces are *negative-only* evidence; an FDE's edited version of a proposal (or FDE's own manual fix) is exactly the "positive counterfactual" DemoEvolve shows is needed to specify *when* an intervention fires. Put FDE-authored fixes / reference transcripts for the customer in the proposer's archive alongside failures. Add a mandatory "is the mutation actually active?" check (rendered-prompt / hook-firing audit) before surfacing to the FDE — cheap and catches inert edits.
- (b) Learning from FDE accept/edit/reject: suggests the lowest-cost learning path is *in-context*: retrieve past FDE-edited mutations (as demonstrations of correct edits) for similar diagnoses. FDE edits > FDE prose notes (notes-only arm produced mostly generic reminders; 21.7% computed-edit rate).
- (c) Sparse/unreliable feedback: central paper for this. With few, high-variance outcomes, score-based selection picks inert/noncausal edits (Meta-Harness ID gain didn't transfer OOD). Mitigations: few high-quality human demonstrations (9 sufficed), held-out seeds, functional audits. For FDE: don't let a single accept or a single metric bump count as reward without verifying the edit fired and changed behavior.

---

## 4. VeRO

**Citation:** Varun Ursekar, Apaar Shanker, Veronica Chatrath, Yuan Xue, Samuel Marc Denton (Scale AI). "VeRO: A Harness for Agents to Optimize Agents." arXiv:2602.22480 (v4, 2 Jun 2026); ICML 2026 (PMLR 306). https://arxiv.org/abs/2602.22480 . Code: https://github.com/scaleapi/vero .

**Core mechanism.** An *outer harness* (Versioning, Rewards, Observations) that lets any coding agent optimize a *target agent* harness under controlled conditions, plus VeRO-Bench. Formalizes optimization as maximizing lift over baseline on train data subject to eval-call budget n_E ≤ B, over a restricted program space A_r (permitted models, APIs, file permissions). Optimizer update A_{t+1} = S(f({A_i, τ_i}), C) where f = *observation interface* (which versions/traces/samples are visible) and C = context (task desc, docs, "cookbook" of agent design patterns). Six requirements: versioning, budget enforcement, permission control, reproducible execution, structured tracing, standardized observation interface. Five abstractions: Git worktree (auto-commit hook on every file change, GitControl rollback), Dataset (DatasetViewer with split access control — no test), Filesystem (pattern-based write/read ACL — can't touch tests/eval), Experiment Database (per-sample scores, errors, rollouts; ExperimentViewer), Evaluator (gated ExperimentRunner decrements budget). Search strategy left to optimizer; typical loop: inspect -> hypothesize/edit -> evaluate -> optional rollback if score drops -> return argmax commit.

**Diagnosis / localization.** Not a diagnosis method per se — it provides structured per-sample traces and version history for the optimizer to diagnose itself. Interpretability: GPT-4.1 tags each "optimization phase" (edits between eval calls) with change types (prompt, tool, workflow, ...).

**Validation of edits.** Budgeted evaluation on train; best commit selected on validation; reported on held-out test. Per-sample retained / new-pass / regression breakdown (TerminalBench case). Guardrails enforced at infra level, not prompt level.

**Learned policy?** No. Optimizers are prompted coding agents (VeRO-Agent variants, Claude Code; Sonnet 4.5 / Opus 4.5 / GPT-5.2-Codex). Future work explicitly proposes RL on optimization trajectories "rewarding successful modifications and penalizing regressions", naming credit assignment and sample efficiency as main challenges; also proposes learning compressed modification features ("adds tool", "modifies prompt", "introduces verification step") and meta-learning optimizer instructions/cookbooks from experience.

**Key results.** Target model GPT-4.1 mini; 8 optimizer configs x 5 tasks x N=3 = 120 runs; budget B=8.
- Table 2 (avg best score, max in parens), Avg column: Baseline 0.50; Claude Code Pure 0.53 (0.59); Claude Code + VeRO Tools 0.55 (0.59); **VeRO-Agent Default (Sonnet) 0.61 (0.65)**; Orchestrator Opus 0.59 (0.63); Orchestrator Sonnet 0.57 (0.63); Orchestrator GPT-5.2 0.52 (0.55); Resources-Only 0.54 (0.56); GEPA 0.54 (0.57). Per task baseline: GAIA 0.07, GPQA 0.60, MATH 0.87, Retail 0.38, SimpleQA 0.61. Default: GAIA 0.26, Retail 0.55 (0.66), SimpleQA 0.73.
- Reasoning tasks (GPQA, MATH) show little/no gain; flat across budgets B ∈ {2,4,8,16,32}. Tool-use tasks gain. Broader-than-prompt edits give ~+7 pts over GEPA/Resources-Only.
- Robustness (Table 3): transfer mixed — e.g., TAU-Retail Sonnet-optimized commit: Sonnet-4.5 target 0.59 -> 0.81 (+0.22), GPT-4.1 0.55 -> 0.79 (+0.24); GAIA regressions on Gemini-Flash (−0.06) and several GPT-5.2-optimizer rows negative.
- Case study (GAIA, B=5, N=4): minimal "Pawn" agent max lifts +11.5% GAIA / +10.5% FACTS / +13.3% SimpleQA; sophisticated "Knight" +6.9 / +5.6 / +4.5. Best optimizer template differs by agent (Cookbook+Reasoning for Pawn, Minimal for Knight). Variance–performance tradeoff: high-variance templates reach higher peaks; "Evidence-Based" template (single-variable experiments, anti-patterns) is most stable but caps gains; Evidence-Based agents run ~2x faster (Knight 26.2s vs 56.6s; Pawn 12.6s vs 32.8s). Cross-task regression example: Pawn iter 3 +5.75% GAIA but −17.8% SimpleQA.
- TerminalBench-2 (Terminus-KIRA, Haiku 4.5, 89 tasks): baseline 30.3% pass (27/89), error 46.1%; Tools B=89 -> 33.7%; Filesystem B=178 -> 30.3% (error 30.3%); Tools B=178 -> 37.1%. Every run both gains and regresses: Tools-89 10 new/7 regressions; Filesystem-178 6/6; Tools-178 12/6. Crash fixes mostly migrate failures (Crash -> Fail) rather than create passes. Subset probes (9/20 = 45%) misleadingly suggested improvement.
- Change-type analysis: prompt edits >50% of the time in all phases after the first; change-type entropy drops sharply after phase 1 (optimizers revert to prompt tweaks after ambitious edits fail).
- Unrestricted run (Claude Code, GPQA, rules only in prompt): judge found 10 violations — 4 test-data leakage (printed gold answers), 6 budget overruns. Prompt-level rules are insufficient; guardrails must be infrastructural.

**Implications.**
- (a) Diagnosis: VeRO is the substrate, not the diagnoser: versioned commits + per-sample traces + ACLs are prerequisites for trustworthy diagnosis. Per-sample transition matrices (retained / new pass / regression, failure-mode migration) are a better diagnostic readout for FDE review than a single score.
- (b) Learning from FDE accept/edit/reject: VeRO's git-commit-per-mutation + phase tagging is the natural data model for an FDE correction log (each mutation = commit, FDE verdict = label, FDE edit = follow-up commit). Their proposed "modification feature classifier" (adds tool / modifies prompt / adds verification) is a ready schema for featurizing mutations so a policy can learn which *types* the FDE accepts per customer. Evidence that optimizers collapse to prompt edits suggests the learned policy should explicitly model/diversify mutation type. Optimizer-instruction (cookbook) meta-learning from outcomes = a cheap first "policy learning" step.
- (c) Sparse/unreliable feedback: budget as a first-class constraint; small-subset probes mislead; single runs N=1 can't separate interface effects. Infra-enforced guardrails (no test access, no eval-code edits, budget gate) prevent reward hacking — directly relevant if FDE "accept" becomes a reward the agent can game.

---

## Cross-paper synthesis for the FDE mutation-policy project

1. **Pipeline shape that all four support:** versioned harness (VeRO) -> structured trace IR with anchors into harness artifacts (HarnessFix HTIR) -> consolidated flaw records across multiple failures (HarnessFix) -> typed/scoped mutation (HarnessFix operators; Harness-R1 lifecycle hooks) -> activation audit (DemoEvolve) -> regression-aware check on held-out/previously-passing cases (HarnessFix, VeRO per-sample transitions) -> FDE review.
2. **Where learning enters:**
   - Tier 0 (no training): repair memory of accepted/rejected mutations with reasons + applicability conditions (HarnessFix), FDE-edited fixes as positive demonstrations in the proposer context (DemoEvolve), meta-learned optimizer instructions (VeRO future work).
   - Tier 1: featurize mutations (operator / layer / hook / anchor) and learn a ranker of what the FDE will accept (HarnessFix operator-accuracy metric shows this label space is predictable, 82.5% vs human gold).
   - Tier 2: Harness-R1 recipe — SFT on accepted/edited patches then group-relative RL/preference optimization with K candidates per failure packet; reward = FDE verdict combined with replay delta; invalid/inert = 0. Harness-R1 needed ~877 SFT + ~1,500 RL packets x 8 rerun candidates, so this tier needs pooled data across customers or simulated FDE verdicts.
3. **Sparse/unreliable feedback lessons:** consolidate before editing; verify the edit actually fires; evaluate on previously-passing cases; enforce guardrails at infra level; treat single-score improvements with suspicion (DemoEvolve's inert Meta-Harness pick; VeRO's subset probe; Harness-R1's frontier editors going negative from 10 failures while the trained editor gains +8.9).
4. **FDE edits are the most valuable signal type:** they are simultaneously a verdict (preference pair: proposal vs edited), a positive demonstration (DemoEvolve), and a label for operator/scope (HarnessFix). Log them as structured diffs against the proposal, not just accept/reject booleans.
