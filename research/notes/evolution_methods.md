# Harness Evolution Methods: Notes for the Self-Evolving FDE Harness Project

Scope: five 2026 papers on automatic harness evolution. For each one: the mechanism, how it uses history (relevant to our append-only episodic memory), how it handles overfitting, component interference and generalization, key numbers, and what we should borrow.

Method: I downloaded all five PDFs from arxiv.org/pdf/<id> and extracted the full text with pypdf. I read each paper in full, including appendices. Every number below is copied from the paper text. Anything I inferred myself is labeled "(our inference)".

---

## 1. Meta-Harness: End-to-End Optimization of Model Harnesses

- Citation: Yoonho Lee, Roshen Nair, Qizheng Zhang, Kangwook Lee, Omar Khattab, Chelsea Finn. "Meta-Harness: End-to-End Optimization of Model Harnesses." arXiv:2603.28052v1, 30 Mar 2026. Stanford / KRAFTON / MIT.
- URL: https://arxiv.org/abs/2603.28052 (project page https://yoonholee.com/meta-harness/, artifact https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact)

### Core mechanism
- The outer loop is deliberately minimal. A single coding-agent proposer (Claude Code with Opus-4.6) reads a growing **filesystem D**. D holds one directory per evaluated candidate, containing its source code, scores and raw execution traces (prompts, tool calls, outputs, state updates).
- Each iteration: the proposer queries D with grep/cat, forms a failure hypothesis, and writes k new harnesses. Each candidate must pass interface validation, then is evaluated, and everything is logged back into D (Algorithm 1).
- The loop keeps a population and a **Pareto frontier** (e.g., accuracy vs. context tokens). There is **no parent-selection rule and no mutation operators**: the proposer may inspect any prior candidate and decide between a local edit and a full rewrite.
- A harness is a single-file Python program covering prompting, retrieval, memory and orchestration. A typical run evaluates about 60 harnesses over 20 iterations.
- A short domain "skill" tells the proposer where to write, how to inspect history, and which files it may and may not modify.

### Use of history (most relevant to episodic memory)
- The central claim is that **full, uncompressed history beats summaries**. Table 1 compares context per iteration: OPRO 0.002, TextGrad 0.015, AlphaEvolve 0.022, GEPA 0.008, Feedback Descent 0.012, TTT-Discover 0.026, Meta-Harness 10.0 MTok/iter. A single evaluation can generate up to 10M tokens of diagnostics.
- Proposer access statistics on TerminalBench-2 (10 iterations): a median of **82 files read per iteration** (range 69–99). The reads split 41% harness source, 40% execution traces, 6% score/summary files, 13% other. The proposer references more than 20 prior candidates per step, so its access is non-Markovian.
- Ablation (Table 3, text classification, median / best accuracy / number of runs above zero-shot):
  - Scores only: 34.6 / 41.3 / 26.
  - Scores + LLM summary: 34.9 / 38.7 / 23.
  - Full traces: **50.0 / 56.7 / 39**.
  - Summaries did not recover the missing signal and slightly hurt the best candidate. **Raw traces are the key ingredient.**
- Qualitative trajectory on TerminalBench-2 (Appendix A.2):
  - Iterations 1–2 bundled structural bugfixes with prompt edits. Both regressed: −5.6pp and −6.7pp from the 64.4% baseline.
  - In iteration 3 the proposer diagnosed the **confound** (the shared prompt edit) and isolated the structural fix. That candidate scored −1.1pp.
  - After six regressions it concluded that "modifications to prompts and completion flow are high risk" and pivoted to a **purely additive** change (an environment snapshot before the first turn). That became the best candidate.
  - It then composed "orthogonal fixes" and transferred lessons from a *separate earlier run* ("don't cleanup service artifacts was worth +18pp").

### Overfitting, interference and generalization
- The proposer never sees test results. Selection uses only the search set, and the final test evaluation runs only on the Pareto frontier.
- Code-space regularization: "coding models tend to propose coherent algorithms rather than brittle, hard-coded solutions." Overfitting is also inspectable, since brittle if-chains and hard-coded class maps are visible in code.
- On TerminalBench-2, search and evaluation used the same 89 tasks (framed as a "discovery problem"). Overfitting was checked by manual inspection plus **regex audits for task-specific string leakage** into evolved harnesses.
- Interference is handled emergently, not by design. The proposer itself isolates confounded edits and prefers additive changes.
- Generalization evidence: nine OOD classification datasets, and transfer of a math retrieval harness to four unseen models.

### Key results (exact)
- Online text classification (GPT-OSS-120B): **48.6% avg vs. ACE 40.9 (+7.7) and MCE 40.0 (+8.6)**, using 11.4K context vs. 50.8K (ACE) and 28.5K (MCE), i.e., about 4× fewer tokens. Per dataset: USPTO 14.0, S2D 86.8, Law 45.0.
- Against text optimizers on the search set (median / best): GEPA 32.6/40.2, Best-of-N 34.0/44.2, OpenEvolve 39.1/43.3, TTT-Discover 34.1/45.6, **Meta-Harness 50.0/56.7**. It matched OpenEvolve and TTT-Discover's final accuracy within 4 evaluations, i.e., 0.1× the evaluations.
- OOD classification (9 datasets): **73.1 avg vs. ACE 70.2** (+2.9). Best on 6/9. Additional context 7.3K vs. 11.7K.
- Retrieval-augmented IMO-level math (200 problems, 5 held-out models): 38.8 avg vs. 34.1 with no retriever (**+4.7**) and 37.5 with BM25 (+1.3). The search took 40 iterations and produced 109 candidates on a 250-problem search set.
- TerminalBench-2: Opus 4.6 scored **76.4%** vs. Terminus-KIRA 74.7 (#2 among Opus 4.6 agents). Haiku 4.5 scored **37.6%** vs. Goose 35.5 (#1). The winning change was an environment bootstrap of about 80 lines, which gained on 7 of 89 tasks.

### Practical tips (Appendix D, directly reusable)
- The skill text is the strongest lever. It should constrain outputs and forbidden actions, not the proposer's diagnosis procedure. Iterating on the skill mattered more than iteration count or population size. Run a few 3–5 iteration debug runs first.
- Build the search set from examples the baseline gets **wrong**. Keep it small enough for about 50 full evaluations (50–100 examples). A fast, discriminative eval beats a large one.
- Log in navigable, machine-readable JSON with consistent names and a hierarchical layout.
- Provide a small CLI that lists the Pareto frontier, shows the top-k, and **diffs code and results between two runs**.
- Run a cheap validation test (import, instantiate, call on a tiny set) before any expensive eval.
- Run evals outside the proposer.

### What we should borrow
1. **Episodic memory as a queryable raw-trace store, not summaries.** Store every proposal's diff, full harness snapshot, eval traces, scores and FDE verdict (with rationale). Give the proposer tools (grep-like search, `list_frontier`, `diff(v_i, v_j)`, `show_traces(v, failed_only)`) instead of a pre-packed prompt. In MongoDB terms: one document per proposal, with trace blobs referenced and queryable.
2. **Proposals must state a hypothesis plus the failure evidence** (trace IDs) behind it. This matches the proposer's quoted "Hypothesis: …" logs and makes FDE review much faster.
3. **Confound discipline.** Discourage bundling prompt edits with control-logic edits in one proposal. Prefer additive changes. We can nudge this via the proposer skill, or by flagging a proposal as "multi-component" in the review UI (our inference).
4. **Leakage audit.** Regex-check proposed harness changes for customer-eval-specific strings, i.e., hard-coded answers or case IDs.
5. **Cheap interface validation gate** before any eval. **Pareto view** (quality vs. cost/latency/context) instead of a single score.
6. **Cross-run lesson transfer.** Allow the proposer to read other deployments' histories, subject to customer data boundaries (our inference).

---
## 2. HarnessCompass: Guiding Automatic Harness Evolution toward Generalizable and Effective Agent Harnesses

- Citation: Luan Zhang, Ruochen Zhou, Dandan Song, Zhengyu Chen, Yuhang Tian, Jun Yang, Huipeng Ma, Chenhao Li, Guangyuan Feng, Xudong Li, Yizhou Jin, Yan Xu. arXiv:2608.01918v1, 3 Aug 2026 (under review). Beijing Institute of Technology / CityU HK.
- URL: https://arxiv.org/abs/2608.01918
- Builds on AHE (Agentic Harness Engineering, Lin et al. 2026, arXiv:2604.25850). Its harness has seven component types:
  - **Structural:** tool implementations, middleware, sub-agent configs.
  - **Guidance:** system prompt, tool descriptions, skills, long-term memory.

### Core mechanism (three principles, Algorithm 1)
1. **Constrained evolution via a "Generalization Gate."** The gate lives in the meta-agent system prompt and applies to all seven surfaces. It has two parts:
   - (a) **Content ban.** No task/instance IDs, no test names, no private symbols or paths of the code under test, and no code branches keyword-matching task-specific tokens. It also bans "Iteration N showed task X needs change Y" recitations. Only cross-task principles *with an explicit applicability criterion* are allowed. The litmus test: "Would this still help a task from a library I have never seen?"
   - (b) **Placement rule.** *Capability* edits must be executable code (middleware/tools/sub-agents). *Guidance* edits must go in the prompt or memory. A structural change that only injects advisory text is rejected as "guidance dressed up as structure."
   - Memory-writing rules: one principle per entry plus its applicability criterion. Scan existing memory first. **Merge duplicates and contradictions into one "deciding criterion"** instead of stacking them. Prune every iteration.
2. **Proactive (first-person) feedback,** a four-stage pipeline per failed task:
   - (1) A **blind report**: the same base model reviews its own trajectory *without* the verdict, reporting harness friction and wished-for capabilities as JSON with trace_refs and severity. This avoids hindsight rationalization.
   - (2) A **hindsight report** with the verdict, including `failure_attribution` ∈ {harness, agent_reasoning, task_ambiguity, environment}. Non-harness failures are discarded.
   - (3) **Reconciliation** of the two reports, recording `self_consistency` ∈ {pre_post_agree, partial, conflict}.
   - (4) **Grounding** by an analyzer model. Complaints about existing components need direct trace evidence. New-capability requests need a trace-demonstrated gap. Each surviving item is routed to a structural or guidance track.
   - Aggregation is deterministic, with no LLM call: group by component, then compute confidence from agreement, number of distinct tasks affected, and blind/hindsight consistency. The meta-agent is told this evidence is **subordinate** to trajectory evidence.
3. **Component-wise optimization plus the R³ merge.**
   - Each round runs **two meta-agents in parallel on disjoint component tracks**: a structural-only variant and a guidance-only variant. Each has a hard boundary self-check and reverts any cross-track edit. Both variants are evaluated.
   - The winner becomes the immutable base in a git worktree. **R³** then salvages the loser's diff in three steps:
     - **Revision:** keep each loser change only if it is independently beneficial and non-conflicting; "when unsure, DROP".
     - **Recombination:** the winner wins file conflicts.
     - **Refinement:** remove redundancy. If an advisory prompt or memory item is already enforced deterministically by middleware or a tool, delete the advisory one. This counters prompt and memory bloat, "a real failure mode in past runs."
   - Output: `integration_manifest.json` (kept_from_loser, dropped_from_loser, removed_as_redundant, each with a "why").
   - **Acceptance:** the merged harness replaces H* only if the winner's Pass@1 beats the current harness.
- The loop starts from a deliberately **minimal seed** H0 (a bash tool plus a short prompt), so every later component is introduced and measured by the loop itself.

### Use of history
- Every meta-agent edit produces a **change manifest**. Its fields are id, type (new/improvement/rollback), description, files, `failure_pattern`, **`predicted_fixes`** (tasks expected to flip), **`risk_tasks`**, `constraint_level`, `why_this_component`, `agent_feedback_evidence` (feedback IDs) and `feedback_confidence`.
- "The next round uses [the manifest] to attribute score changes to individual edits and determine rollbacks." Edits that do not help are reverted in the next round (the "falsification loop").
- The R³ integrator receives per-variant evaluation evidence ("which tasks each flipped / regressed").
- History here is mostly the **previous round** plus the evolving memory file. There is no large archive (contrast with Meta-Harness and DREvo).

### Overfitting, interference and generalization
- **Overfitting:** handled by the Generalization Gate plus a strict split (50 evolution tasks vs. 450 held-out tasks never seen).
- **Case study:** ungated memory accumulated answer-key entries, e.g., "django__django-13158 regressed because…" or "sympy__sympy-14711 … patch Vector.__add__ first". Gated memory held criteria such as the "Execution-path ownership rule" and the "Consumer-count scope rule", each with an applicability clause.
- **Interference:** handled by the disjoint component tracks plus R³.
- **Misattribution:** handled by grounded first-person feedback and failure attribution.
- **Caveat the authors report:** feedback without R³ raised the sample score but *reduced* held-out performance (it overfit). The cross-model transfer was also uneven: pytest −10.5 and sphinx −4.5 on Sonnet 4.6.

### Key results (exact; SWE-bench Verified, GPT-5.4 non-thinking, k=2 rollouts)

Main results (Table 1). "Sample" is the 50-task evolution set; "Held-out" is the 450 unseen tasks.

| Harness | Sample | Turns | Held-out | Total (500) |
|---|---|---|---|---|
| Seed H0 | 54.0 | 0 | 51.6 | 51.8 |
| AHE | 63.0 | 20 | 54.7 | 55.5 |
| HarnessCompass | **66.0** | **5** | **60.4** | **61.0** |

Ablation (Table 2, cumulative, each row adds one principle):

| Configuration | Sample | Turns | Held-out | Total |
|---|---|---|---|---|
| + Generalization Gate | 62.0 | 2 | 58.4 | 58.8 |
| + Proactive Feedback | 66.0 | 12 | **55.8** (held-out drops) | 56.8 |
| + R³ | 66.0 | 5 | 60.4 | 61.0 |

- Cross-model transfer (Table 3): the harness evolved on GPT-5.4 was frozen and run on Claude-Sonnet-4.6. Total went 70.0 → 73.8, sample 68.0 → 76.0, held-out 70.2 → 73.6.
- Per repository (GPT-5.4): django 59.3 → 70.1 (+10.8), sphinx 35.2 → 58.0 (+22.8), pytest 52.6 → 68.4 (+15.8), scikit-learn 73.4 → 68.8 (−4.6). The total gain is +9.2.
- Changes that landed during evolution (Fig. 2):
  - Canonical boundary normalizer plus read-after-write smoke check (prompt + tool).
  - Patch-verdict guard that blocks finalizing on failing validation (middleware).
  - Isolated-venv test runner plus runtime-failure routing (tool + middleware).

### What we should borrow
1. **A Generalization Gate as an automated pre-review lint** on every proposal before the FDE sees it:
   - Reject proposals that hard-code customer ticket IDs, eval case IDs, specific entity names or keyword branches.
   - Require every context/skill/memory rule to carry an **applicability criterion** ("when this applies / when it doesn't").
   - For an FDE harness, the "task-specific" line is subtler, since customer-specific facts are *legitimately* part of the harness. Our gate should ban **eval-instance** specifics, not customer-domain specifics (our inference).
2. **Proposal manifest schema.** Adopt HarnessCompass's change manifest nearly verbatim as the proposal document in episodic memory: `failure_pattern`, `predicted_fixes`, `risk_tasks`, `component`, `why_this_component` and `evidence_refs`. After evaluation, record the actual flips and regressions against the predictions. **Prediction accuracy becomes a per-proposal calibration signal**, useful to the FDE and for trusting the proposer (our inference).
3. **Placement rule, "deterministic, not advisory."** If a behavior can be enforced by a tool or control logic, don't encode it as prompt text. The R³ Refinement step (delete advisory text already enforced by code) is a good periodic "harness hygiene" proposal type.
4. **Memory hygiene.** Merge contradictory rules into one deciding criterion. Prune each cycle. This applies directly to our mutable procedural memory (the current harness context and skills).
5. **Track separation.** Generate proposals for different component classes (tools/control vs. context/skills/retrieval) separately, so each FDE decision and eval result is attributable. When several are accepted, run an R³-style merge that drops redundant or conflicting items with a logged rationale.
6. **Blind-then-hindsight self-reports with failure attribution** (harness / agent reasoning / task ambiguity / environment). Filter out failures the harness can't fix, e.g., customer-data ambiguity. Also useful for FDE triage.
7. **Accept only if strictly better than the incumbent** on the eval, and keep a held-out eval split the proposer never sees.

---
## 3. DREvo: Distilling Recalibrated Historical Experience for Harness Self-Evolution

- Citation: Hanghui Guo, Weijie Shi, Zhangze Chen, Shengxiang Xu, Yishu Wang, Yimei Zhang, Wangze Ni, Jia Zhu, Shimin Di. arXiv:2607.26722v2, 12 Aug 2026. Southeast Univ. / HKUST / Zhejiang Normal / ZJUT / ZJU.
- URL: https://arxiv.org/abs/2607.26722

### Core mechanism
- **Motivation.** With Meta-Harness under both full-history and compressed-history reuse, accuracy **oscillates across iterations** (regress/recover) rather than climbing. Accumulating history does not by itself give stable search guidance. The authors frame two questions: "What is still valid?" and "Where to evolve next?"
- **(A) Function-level evidence anchoring.**
  - The harness is a set of functional components C (tool use, memory mgmt, parser, retrieval, prompt, …), each anchored to its function implementation f_c.
  - Each iteration parses feedback o_t = (g_t global stats, Q_t per-task outcomes, F_t failure-pattern frequencies such as timeouts, runtime exceptions, tool-call errors, context overflow).
  - It then computes a line-level diff and maps hunks to enclosing functions (FuncDiff). The proposer is **encouraged to modify a single component** per iteration.
  - Each modified component yields an **evidence unit** e = (component, code, diff, feedback, Δ, polarity ρ, weight w, provenance pointer).
  - ρ = +1 if Δ ≥ 0, otherwise −1. Initial **w = 1.0 for a single-component edit and 0.5 for a multi-component edit**, since attribution is less certain.
- **(B) State-dependent recalibration.** Before reuse, each unit gets w_e = harmonic mean of r_t(e) and q_t(e), where:
  - **Historical reliability** r = cons × fresh.
    - cons = Δ-magnitude-weighted fraction of the unit's creation and reuse records whose polarity agrees with the current polarity.
    - fresh = 0.9^(t − last_used_iteration).
  - **Structural compatibility** q = 1 − TED(AST_then, AST_now) / (|AST_then| + |AST_now|). This is the AST tree-edit distance of the *anchored component only*, with identifiers normalized but literals, prompt strings and control flow preserved.
  - The polarity of a reused unit is updated by the outcome of each reuse.
- **(C) Role-conditioned search-intent distillation.**
  - Extract the current failure patterns and retrieve evidence tagged with the same failure categories.
  - Partition with θ = 0.5: X = reliable positive (w > θ, ρ = +1), A = reliable negative, T = low-confidence.
  - Role activation (Algorithm 1), in priority order: **Exploit** if X ≠ ∅ (binding: follow or refine), else **Avoid** if A ≠ ∅, else **Explore** if nothing was retrieved or the previous Retest failed, else **Retest** if T ≠ ∅ (non-binding references), else Explore.
  - A generator G then writes an explicit **search intent** s_t = target component + modification direction. The proposer produces h_{t+1} ~ P(· | h_t, s_t).

### Use of history (directly relevant to episodic memory)
- The episodic repository is append-only. What gets recalibrated is a **derived, mutable weight per evidence unit**. This separates the immutable log from a validity score that is re-estimated against the *current* harness state.
- Experience can become stale because a later edit changed the component it was about. It can also be revived: a formerly harmful direction may become viable after state changes, which is what the Retest role is for.
- The proposer context stays bounded at about **2.9K tokens**. Under DREvo's own replication, Meta-Harness's context grows past 5.3K tokens with larger oscillations.
- Note: DREvo describes Meta-Harness as reusing "compressed summaries". Meta-Harness itself emphasizes full-filesystem raw traces. DREvo's Fig. 1 tested both full- and compressed-history variants.

### Overfitting, interference and generalization
- **Interference/attribution:** the single-component edit preference plus down-weighting multi-component edits (0.5).
- **Robustness to state drift:** Claude Opus 4.6 randomly modified one component of the final harness, across 16 settings (4 drift types × 4 benchmarks). Blind evidence reuse averaged **−5.3 pts**. DREvo averaged **+0.6 pts** and maintained or improved performance in **11/16** settings (blind reuse: 2). The largest gap was S2D prompt drift: −10.0 → +6.0.
- **Generalization is weak by the authors' own admission.** On agentic tasks, evolution and evaluation ran on the same benchmark suites with no split, and the authors state "the reported gains reflect benchmark-specific harness adaptation rather than generalizable improvements on unseen tasks." Domain reasoning tasks did have validation/test splits.
- Setup: the proposer was Claude Opus 4.6 (1M context). Evaluation models were GPT-OSS-120B (reasoning) and DeepSeek-V4-Flash, non-thinking (agentic). Runs used 20 iterations (reasoning) and 10 (agentic). The agentic seed was Terminus-KIRA.

### Key results (exact)
- Domain reasoning test accuracy:

| Dataset | DREvo | Second best | Margin |
|---|---|---|---|
| USPTO | **25.0** | ACE 16.0 | +9.0 |
| S2D | **89.2** | Meta-harness 86.8 | +2.4 |
| Law | **49.0** | Meta-harness 45.0 | +4.0 |

- Agentic, TB2 (DeepSeek-V4-Flash): **42.7** vs. Terminus-2 34.8 and Meta-harness 29.2. By difficulty: Easy 75.0, Med 49.1, Hard 26.7.
- Agentic, SWE-bench Verified: **67.6** vs. Mini-SWE-Agent 66.8, OpenHands 61.8, AHE 61.8, Meta-harness 38.6.
- Average gains: the abstract says 16.2% (reasoning) and **13.8%** (agentic), but the contributions list says 14.2% for agentic. The paper is internally inconsistent here.
- Ablation (A = anchoring, R = recalibration, D = distillation), USPTO / S2D / Law / TB2-full:

| Configuration | USPTO | S2D | Law | TB2 |
|---|---|---|---|---|
| None | 12.0 | 78.8 | 34.0 | 29.2 |
| A | 20.0 | 81.1 | 37.0 | 29.2 |
| A+R | 23.0 | 86.3 | 39.0 | 35.9 |
| A+D | 18.0 | 84.0 | 42.0 | 37.1 |
| A+R+D | 25.0 | 89.2 | 49.0 | 42.7 |

- Caveat (our inference): Meta-harness's TB2 and SWE numbers here come from DREvo's own reruns with a different base model, so they are not comparable to Meta-Harness's own paper.

### What we should borrow
1. **Evidence units in episodic memory, anchored to harness components.** Every proposal outcome (FDE accept/edit/reject plus eval Δ) becomes one or more evidence units keyed by the **component ID** it touched: context block, skill, tool, control step, retrieval config or eval. Store polarity and provenance. Multi-component proposals get lower attribution weight.
2. **Recalibrated validity as a derived view over the immutable log.** This fits our design exactly: the episodic log is append-only, while the validity weight is recomputed against the *current* procedural memory.
   - Freshness decay: 0.9^Δiterations.
   - Consistency: agreement of past uses.
   - Structural compatibility: how much the target component has changed since the evidence was recorded. For prompts and skills, use text or AST diff similarity.
   - When a component has been rewritten, old "this didn't work" evidence should lose force.
3. **Roles for proposal generation (Exploit / Avoid / Retest / Explore).** Label each proposal with its role and show it to the FDE. Treat **FDE rejections as strong negative evidence (Avoid)**. Let stale rejections decay to Retest once the component has changed significantly. This avoids permanently blacklisting ideas the FDE rejected under different circumstances (our inference).
4. **Failure-pattern taxonomy** (timeout, tool-call error, context overflow, …) as the retrieval key from current failures to past evidence. MongoDB indexes on {component, failure_category} make this cheap.
5. **Bounded proposer context via distilled intent.** This contrasts with Meta-Harness's full-history approach. A reasonable hybrid (our inference): give the proposer a distilled intent, plus tool access to drill into raw traces when needed.

---
## 4. Hierarchical Self-Improvement (HSI): A Framework for Task-Specific Evolvable Agent Harnesses

- Citation: Tailin Zhou (HKUST). "Hierarchical Self-Improvement: A Framework for Task-Specific Evolvable Agent Harnesses." arXiv:2608.08466v1, 9 Aug 2026. Single author, framed as an "initial exploration."
- URL: https://arxiv.org/abs/2608.08466. Code: https://github.com/TailinZhou/hsi

### Core mechanism
- **One frozen LLM operates at three scopes**, each with disjoint editable surfaces, separate memory/histories and a shared `react()` primitive:
  - The **task harness H** runs tasks. It is hot-swappable behind a fixed `using_harness(agent, task)` injection seam.
  - The **evolver** rewrites H using the strategy Σ.
  - The **meta-evolver** rewrites Σ itself: seed policy, evolution policy, commit policy, best-version selector.
  - The meta-evolver's own execution logic is an **immutable "frozen outer anchor"** (M → H → Σ → frozen anchor). Edits outside a scope's authorized directory are rejected.
- **Five stages per run:**
  1. **Seed selection = hypothesis generation.** Pick an ancestor from the evolution graph and emit a structured hypothesis: anchor version, motivation, expected improvement direction, and a **falsification criterion**. A seed-validation probe runs up to 3 evaluate() calls.
  2. **Main evolution.** Free-form rewrites of prompts, tools, memory, state, hooks and policies. The model decides when to inspect, edit, evaluate or stop, with at most 80 react() steps.
  3. **Commit selection** into a **diverse multi-commit pool**, not just the argmax. Each commit carries an LLM-written semantic rationale.
  4. **Meta-evolution** of Σ, with at most 50 steps.
  5. **Generalization-first best-version export** on validation performance. This stage is fixed and non-evolvable.
- **Thinking-on/off design:** reasoning is disabled for task execution (temperature 0) and enabled for evolver and meta-evolver. This isolates gains from harness changes and excludes gains from more inference-time reasoning.
- **Noise-robust selection:** candidates are ranked by a lower confidence bound, r = μ − zσ/√n with z = 0.5.
- Principle 2: there is no prescribed explore/exploit schedule. The strategy is itself evolvable.

### Use of history (three memory channels, Appendix A.3–A.4)
- **Iteration-local `plan.md`:** scratch hypotheses. It is **rolled back together with the code** if the candidate is discarded.
- **Persistent `BOOTSTRAP.md` lesson archive:** discovered patterns, failed directions, reusable guidance. Written via an explicit `lesson` tool.
- **Cumulative evolution graph G_t:**
  - Nodes = committed harness snapshots with reward and metadata.
  - **Edges = semantic relations** ("extends", "repairs failure mode", "explores different direction").
  - Seed selection reasons over successful, failed and unexplored branches.
- **Probe mechanism:** instead of exposing raw trajectories, a query-driven auxiliary process returns compact summaries, e.g., "which seed-selection behaviors correlate with successful iterations", "which evolution patterns frequently lead to regression". This keeps context bounded. (It is the opposite of Meta-Harness's choice.)
- The meta-evolver turns local discoveries into reusable evolution heuristics. Examples: "prioritize structured state representations over raw observations", "avoid overly aggressive exploration near a plateau", and a codified "LLM targets, BFS navigates" pattern.

### Overfitting, interference and generalization
- **The stance is explicitly task-specific:** each task family keeps its own harness. The author argues against the assumption of one universal harness, citing Wang et al. 2026b (arXiv:2607.12227), which found harness evolution often loses to parallel sampling and gains only +0.6pp on disjoint splits.
- **Evaluation and splits stay outside the agent's control.** Setup B uses dev/val/test splits, and the test split is never accessible.
- **Single lineage instead of a population,** chosen for attribution clarity: gains come from redesign, not from candidate throughput.
- **Stated limits:**
  - A **feedback-fidelity bound**: sparse reward means nothing to select on.
  - A **backbone-capability bound**: NLE showed no gain.
- The paper does not specifically address component interference, beyond scope isolation between H and Σ.

### Key results (exact; BALROG, DeepSeek-V4-Flash frozen, T=5 iterations)

Setup A, in-distribution with re-sampled seeds, % Progress:

| Harness | BabyAI | Crafter | TextWorld | MiniHack | NLE | Avg |
|---|---|---|---|---|---|---|
| Init | 42.0 | 11.6 | 40.0 | 0.8 | 0.0 | 18.9 |
| HSI meta-off | 77.3 | 36.4 | 46.0 | 5.8 | 0.0 | 33.1 |
| **HSI meta-on** | **81.3** | **44.6** | **65.0** | **15.8** | 0.2 | **41.4** |

- Gains over init: +39.3, +33.0, +25.0 and +15.0 on BabyAI, Crafter, TextWorld and MiniHack. Meta-evolution adds +19.0 (TextWorld) and +10.0 (MiniHack) over meta-off.
- Setup B, BabaIsAI held-out 20% test split (init → best test, meta-on / meta-off):
  - BreakStop: 0.033 → 0.98 / 1.00.
  - GoTo: 0.18 → 1.00 / 0.96.
  - Make: 0.00 → 0.36 / 0.34.
- Dynamics: the largest gain usually came in iteration 1. Crafter's best was at iteration 4 (dev reward 0.166 → 0.578), with a regression in iteration 5.
- Caveat: this is a single-author, small-budget study (5 iterations, few test repeats). It has no external-proposer baseline, and NLE shows no improvement.

### What we should borrow
1. **Scoped, layered editability with a frozen anchor.** Our analogue:
   - Customer harness = H (context, skills, tools, retrieval, control logic).
   - Proposer strategy = Σ (how proposals are generated, which evidence it reads, how it picks what to change).
   - The FDE review loop, eval runner and splits = frozen anchor, never editable by the agent.
   - Enforce directory/collection-level write permissions per scope.
2. **Structured hypotheses with falsification criteria** on each proposal: anchor version, motivation, expected improvement, "this fails if …". This pairs well with HarnessCompass's predicted_fixes/risk_tasks. The FDE can later check the outcome against the stated criterion.
3. **Evolution graph with semantic edges** in episodic memory. Each accepted or rejected version is a node, with edges typed as extends / repairs / explores-alternative / reverts. This is richer than a linear version list and naturally maps to MongoDB documents with parent refs and edge types.
4. **Multi-commit pool.** Keep several accepted-but-not-deployed variants alive rather than only the deployed head. Useful when the FDE is unsure (our inference).
5. **Scratch notes roll back with rejected candidates.** Keep them in episodic memory but mark them invalidated, so the proposer doesn't treat a rejected proposal's reasoning as current state.
6. **LCB-based ranking** (μ − 0.5σ/√n) for noisy customer evals.
7. **Meta-level learning from FDE feedback.** A "meta-evolver"-style step periodically distills patterns in FDE accept/reject decisions into the proposer's strategy, e.g., "this FDE rejects prompt-only changes to escalation logic". It is bounded by a fixed anchor (our inference).
8. **Honest limits.** Harness evolution only helps where the eval gives an informative signal and the base model is competent. Invest in eval quality first.

---
## 5. HarnessBank: Semantic Gene-Bank Search with Gated Verification for Agent-Harness Self-Evolution

- Citation: Xiaotian Luo, Dizhan Xue, Fengxingyu Wang, Chuanrui Hu, Yafeng Deng. arXiv:2607.13683v2, 30 Jul 2026. EverMind AI / Shanda Group. Code "will be publicly available upon acceptance."
- URL: https://arxiv.org/abs/2607.13683
- Note: HSI (paper 4) cites this arXiv ID under a different title, "Self-evolving agent harnesses via gated semantic quality-diversity" (GSME). That is presumably the v1 title.

### Core mechanism
- **Roles are separated:**
  - A frozen **task agent** runs the tasks.
  - A separate **evolver agent** (Claude Opus 4.8) diagnoses failures and proposes patches.
  - A **deterministic evaluator** handles sampling, scoring, activation logging and statistical tests.
  - The **Harness Gene Bank** stores candidates.
- The harness H = immutable **kernel K** (evaluation, bookkeeping, self-evolution and interface-critical code) ∪ mutable **surface X**.
- **Harness Gene Bank (HGB):** a MAP-Elites-style quality-diversity archive keyed by **semantic cells (where, why)**.
  - *where* ∈ {prompt, knowledge, runtime, config} = the component modified.
  - *why* = an evolving **failure-pathology** set inferred from trajectories, e.g., (runtime, thinking-runaway).
  - Harnesses addressing the same pathology compete within one cell, and only the best survives. Different pathologies coexist.
  - The bank starts empty.
- **Each round:**
  - Parent = quality-biased argmax over {vanilla} ∪ bank.
  - Full diagnosis ledger on the training set: scores, trajectories and eval metadata per task and attempt.
  - The evolver emits offspring, each tagged with (where, why), either **reinvented** from failure trajectories or **recombined** from compatible mechanisms in different cells.
- **Gated Harness Screening** runs on a sampled subset D_sub before any full-train evaluation. Gates are applied sequentially, and the first N passers go to full evaluation:
  - **Validity gate:** infrastructure failures (sandbox crashes, verifier timeouts) trigger repair-and-retry instead of counting as agent failures.
  - **Activation gate:** each patch declares an activation spec and emits a **deterministic beacon** when triggered. A patch that never fires is "inert" and rejected.
  - **Paired significance gate:** δ_i = per-task mean score difference versus the parent, z = mean(δ) / (σ_δ/√n). The gate requires mean(δ) > 0 and **z ≥ 1.96**.
  - **Gain gate:** must beat the parent.
  - The abstract lists four gates. Eq. 15 formally multiplies only validity × activation × significance.
- **Admission:** passers are evaluated on the full train set. Each replaces the cell's incumbent only if its utility is higher (competitive admission). Archive admission is not held-out credit.
- **Stopping:** at most R rounds, or P consecutive rounds without any cell update. The final pick (train argmax) is evaluated once on the sealed test set.

### Use of history
- History lives as an **archive of verified elites indexed by pathology × component**, not as a raw log. The evolver sees the full bank plus the current parent's full diagnosis ledger.
- **Recombination across cells** is the key payoff. On most domains the credited harness stacks mechanisms from more than one cell. "It is the per-cell elite that keeps the second mechanism alive long enough to be recombined at all."
- The *why* label is an LLM hypothesis, not ground truth. On AppWorld the loop misdiagnosed a capability limit as a knowledge gap, and the gate rejected the patch (target task 0/24 → 0/24, p = 1.0). "A wrong label costs at most a rejected candidate, never a bad harness." Labels steer the search; only the gates give credit.

### Overfitting, interference and generalization
- **The archive is keyed on pathology, not tasks, by design:** "an archive keyed on tasks would preserve harnesses indexed by the very tasks used to select them, which overfits by construction."
- The evaluation uses disjoint train/test splits in all seven domains. The test set is never used during evolution, and each test claim is a single comparison.
- **Noise and false elites** (Table 3, TB2 ablation):
  - Without the 2σ gate: deployment is unchanged, but **+2 false elites** enter (one of them inert, its beacon never fired), and the loop never stops (> 20 rounds, the cap).
  - Without confirm + 2σ: −1.6 test and +3 false elites.
  - "Phantom progress" appears in **62–76% of post-convergence rounds** under single-run or K=3-mean crediting. With paired-2σ, the loop stops at the 10-round floor.
  - On TB2 the gate is two-sided: it also culled a significantly *negative* candidate (−6.4%).
- **Train selection is only a lower bound on generalization:** on GDPval, a variant ranked below the winner on train scored higher on test (+11.5 vs. +9.2).
- **Harnesses are model-specific (the cross-model "pathology → patch matching law"):**
  - AppWorld: Qwen 27B fails via empty engagement and is fixed by verify-finalize (+15.4). The 397B and Gemini 3 Flash make careless errors and are fixed by a submit-verify checklist (+13.6, +13.5).
  - Omni-MATH: the 27B-evolved stack transfers to the 397B (+11.0), which shares the pathology. On Gemini, which thinks too little, it is −1.5, while the matched patch gives +15.3.
  - Applying the lever in the wrong direction costs **−15.7**.
  - Transferable value lies in the diagnose–search–verify *process*, not in a universal harness.

### Key results (exact; frozen Qwen3.6-27B task agent, Claude Opus 4.8 evolver, K=3)

Test Pass@1, vanilla → evolved (gain), train→test retention, test Pass@3:

| Domain | Test Pass@1 | Retention | Test Pass@3 |
|---|---|---|---|
| TB2 | 36.1 → 45.4 (+9.3) | 148% | 52.8 → 58.3 |
| LiveCode | 58.1 → 71.8 (+13.7) | 65% | 66.7 → 79.5 |
| Omni-MATH | 54.3 → 66.0 (+11.7) | 92% | 65.0 → 75.0 |
| BrowseComp+ | 16.9 → 30.8 (+13.9) | 86% | 33.8 → 49.2 |
| GDPval | 43.7 → 52.9 (+9.2) | 110% | 58.6 → 67.2 |
| AppWorld | 41.3 → 56.7 (+15.4, z = 6.44, n = 168) | 86% | 67.3 → 75.6 |
| SWE-bench | 47.4 → 52.6 (+5.1) | 37% | 61.5 → 69.2 |

- SWE-bench is **preliminary, not credited** (z = 0.78 at n = 26). The six other test gains are credited, with p from < 1e-4 to 0.033.
- Baselines under the same protocol (same Qwen3.6-27B as task agent *and* proposer, 780–2,310 rollouts each):
  - HarnessBank was credited on 4/5 sealed tests, DGM on 1, GEPA on 0.
  - GEPA found no variant beating its seed on LiveCode in 47 iterations ("thinking-runaway is not prompt-addressable"). Its AppWorld gain washed out (+2.8, z = 0.97).
  - DGM picked a noisy spike on LiveCode (0.733 regressing to 0.533, z = 0.66). On Omni-MATH it **shipped a regression** (−1.1%).
  - Sealed-test figure: AppWorld vanilla 41.3, HarnessBank 56.7, GEPA 44.0, DGM 52.0. LiveCode 58.1 / 71.8 / 58.1 / 59.8. Omni-MATH 54.3 / 66.0 / 54.3 / 53.2. BrowseComp+ 16.9 / 30.8 / 19.0 / 21.2. SWE-bench 47.4 / 52.6 / 47.4 / 56.4 (DGM highest but not credited).
- Two recurring pathologies were each fixed by a distinct *runtime* mechanism:
  - Thinking-runaway empty turns, fixed by selective recovery.
  - Premature/unverified finalization, fixed by a verify-finalize self-check.
  - On five domains a single pathology accounted for 49–88% of vanilla failures.
- The paper internally mixes "+9 to +15.4%" with the abstract's "5.1% to 15.4%". The 5.1 is the uncredited SWE-bench result.

### What we should borrow
1. **Gated screening before the FDE sees a proposal.** Four gates:
   - Validity: re-run infrastructure failures instead of blaming the harness.
   - **Activation:** each proposed context/skill/tool/control change declares when it should fire and logs a beacon when it does. Show the FDE "fired on 7/40 eval cases".
   - **Paired significance:** per-case paired deltas vs. the current harness, z ≥ 1.96 or a looser, documented threshold for small customer evals.
   - Gain.
   - Proposals failing a gate are auto-logged to episodic memory as rejected-by-gate, not shown as recommendations. This saves FDE attention, which is our scarcest resource.
2. **Semantic (component × failure-pathology) index over episodic memory.** Maintain a per-cell elite. Proposals for different pathologies don't displace each other, and later proposals can **recombine** mechanisms from different cells. In MongoDB, a compound key `{component_type, pathology}` with an "elite" pointer per cell is cheap.
3. **Immutable kernel vs. mutable surface.** Eval harness, logging, gates and the FDE-approval path are the kernel. Only the declared surface is proposable. This matches HSI's frozen anchor.
4. **Stop rule: P rounds without any cell update.** A proposer that keeps "finding" noise-level wins burns FDE time.
5. **Pathology labels are hypotheses.** They route search; credit comes only from gated evidence and FDE acceptance.
6. **Customer-specific (model-specific) harnesses are expected.** Don't assume one deployment's winning patch transfers. Transfer the *process* and the pathology→patch library as *candidates*, re-verified per customer (our inference, consistent with the paper's cross-model finding).

---

## Cross-paper synthesis for the FDE harness design

| Concern | Meta-Harness | HarnessCompass | DREvo | HSI | HarnessBank |
|---|---|---|---|---|---|
| History form | Raw filesystem, all candidates | Per-round change manifest + memory file | Function-anchored evidence units with recalibrated weights | Evolution graph (semantic edges) + lesson file + probe summaries | Pathology × component elite archive |
| Proposer context | Unbounded, agent-navigated | Distilled trajectory evidence + grounded feedback | Bounded (~2.9K tokens) search intent | Bounded via probe | Full bank + parent ledger |
| Anti-overfit | Test hidden; code readability; leakage regex | Generalization Gate (content + placement); held-out split | Weak (agentic: no split, admitted) | Test split outside agent control; task-specific stance | Pathology-keyed archive; sealed test; 2σ gate |
| Interference | Emergent (proposer isolates confounds) | Disjoint structural/guidance tracks + R³ merge | Single-component edits preferred; multi-edit weight 0.5 | Scope isolation (H vs. Σ) | Cell-level competition; recombination only of verified elites |
| Acceptance | Pareto frontier on search set | Winner must beat incumbent | Best-of-run | LCB reward; generalization-first export | Validity + activation + paired z ≥ 1.96 + gain |

Proposed episodic-memory proposal record, combining all five (our inference). Fields:
- `proposal_id`, `parent_version`, `component_ids[]` (single preferred), `component_class` (structural | guidance).
- `pathology` (why), `role` (exploit | avoid | retest | explore).
- `hypothesis`, `falsification_criterion`, `predicted_fixes[]`, `risk_cases[]`.
- `evidence_refs[]` (trace IDs + grounded first-person feedback IDs), `diff`.
- `gate_results` {valid, activated (beacon counts), paired_delta, z, gain}, `leakage_lint` {passed, hits}.
- `eval_outcome` {per-case flips/regressions, predicted-vs-actual}.
- `fde_decision` {accept | edit | reject, edited_diff, rationale}.
- `graph_edges[]` (extends | repairs | explores | reverts | recombines).
- A derived and recomputable `validity_weight` (DREvo: consistency × freshness × structural compatibility).

Everything is append-only except the derived weights and the per-cell elite pointers, which are views.

Key tension to resolve: Meta-Harness's evidence says **raw traces beat summaries**: its median proposal beats the best proposal of the summary ablation. DREvo and HSI argue for **bounded, distilled context**, and DREvo's replication shows Meta-Harness oscillating. A practical hybrid gives the proposer a distilled intent and evidence index up front, plus tool access to drill into raw traces on demand (our inference).

Evaluation caveat worth keeping in mind: Wang et al. 2026, "Rethinking the Evaluation of Harness Evolution for Agents" (arXiv:2607.12227, cited by HarnessCompass and HSI), reports that harness evolution can lose to matched parallel sampling and shows only +0.6pp on disjoint search/eval splits. I did not read this paper myself; the figures come from HSI's summary. It is a strong argument for held-out customer evals and statistical gates.
