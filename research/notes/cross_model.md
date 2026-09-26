# Cross-model transfer of harnesses / prompts / scaffolds

Research notes for the "self-evolving FDE deployment harness" project. Hypothesis under test:
agents write good harnesses for themselves, but these do not transfer across runtime models
(harness–model co-adaptation). All numbers below are taken from full-text reads of the PDFs
(extracted with pypdf) unless explicitly flagged otherwise.

---

## 1. Harness-Bench (arXiv 2605.27922)

**Citation.** Yao, Tan, Liu, Li, Wang, Yu, Tan, Tian, Zhao, Sun, Zhang, Yang (Peking Univ. / Qiyuan Tech).
"Harness-Bench: Measuring Harness Effects across Models in Realistic Agent Workflows." arXiv:2605.27922, 27 May 2026.
https://arxiv.org/abs/2605.27922 — code: https://github.com/Qihoo360/harness-bench
Read status: full text (16 pp. incl. appendix). Fig. 3 left panel (per-model mean/variance scatter) is an image;
per-model variance values could not be extracted as numbers — only the qualitative trend is reported below.

**Setup.**
- 106 sandboxed, offline, oracle-checkable tasks in 8 categories (SWE 22, Data/BI/Finance 14, Workspace/Tool 15,
  Knowledge/Evidence 13, Office 12, Vertical professional 12, Long-running/state 11, SRE/DevOps 7).
- Full factorial: 6 configurable harnesses (OpenClaw, ZeroClaw, Hermes, Moltis, NullClaw, NanoBot) x 8 API models
  (claude-opus-4.6, claude-sonnet-4.6, gemini-3.1-pro-preview, qwen3.6-plus, glm-5.1, kimi-k2.5, gpt-5.4,
  deepseek-v4-flash) x 106 tasks = 5,088 trajectories, + 106 Codex (model-bound) runs = 5,194.
- Harness is *off-the-shelf, not optimized*: each keeps native prompting, action format, tool interface, state policy,
  retry/recovery. Fixed: task, sandbox, budget, timeout, evaluator.
- Score = Security(0/1) x Completion x mean(Robustness, ToolUse, Consistency); process judged by claude-sonnet-4.6.

**Key numbers (Table 2, averaged over 106 tasks x 8 models).**

| Harness | Score | Comp. | Tool | Cons. | Rob. | Tok (K) | Turns |
|---|---|---|---|---|---|---|---|
| OpenClaw | 52.4 | 60.0 | 79.5 | 74.0 | 70.9 | 82.1 | 5.0 |
| NanoBot | 76.2 | 81.6 | 93.8 | 93.7 | 91.7 | 68.7 | 7.3 |
| Hermes | 71.2 | 80.4 | 88.5 | 88.4 | 85.5 | 139.7 | 22.6 |
| ZeroClaw | 61.4 | 69.9 | 84.1 | 83.2 | 79.0 | 133.2 | 8.6 |
| NullClaw | 64.4 | 75.9 | 85.3 | 81.4 | 78.3 | 175.1 | 12.1 |
| Moltis | 68.8 | 78.4 | 86.3 | 87.3 | 84.1 | 134.9 | 8.0 |
| Codex (GPT-5.4, model-bound) | 80.4 | 86.5 | 92.4 | 93.9 | 91.6 | 86.1 | 5.0 |

- 23.8-point spread between best (NanoBot) and worst (OpenClaw) harness on the same model pool. Security 100% everywhere.
- GPT-5.4-only comparison (Fig. 3 right, decoded from figure text): NanoBot 0.8132, Codex 0.8041, Moltis 0.7437,
  Hermes 0.7400, OpenClaw 0.6928, NullClaw 0.6885, ZeroClaw 0.5432 -> even the vendor's own co-designed harness
  (Codex) is slightly beaten by a generic lightweight harness; harness choice alone spans ~27 points for one model.
- Harness dependence (Fig. 3 left): stronger backends have higher mean AND lower cross-harness variance; weaker
  backends are much more sensitive to harness. (Exact per-model variances not extractable.)
- Category-level cross-harness variance (Fig. 4): Data/BI/Finance 0.0155, Workspace/Tool 0.0130, SWE 0.0102,
  Knowledge/Evidence 0.0094, Long-running/state 0.0091, Vertical professional 0.0056, SRE/DevOps 0.0049,
  Office/Business comms 0.0020. Harness matters most for structured data, tool sequencing, workspace state; least
  for language-centric tasks.
- Failure symptoms among failed trajectories (Table 3, non-exclusive): contract/format 36.4%, tool/recovery 24.6%,
  evidence/grounding 14.6%, artifact commitment 11.1%, state/continuation 9.3%.
- More tokens != better: NanoBot top score with the fewest tokens (68.7K).

**What does / doesn't transfer and why.**
- Harness-Bench does not optimize harnesses, so it doesn't test transfer of *evolved* harnesses directly. It shows
  the precondition: the model x harness interaction is large, and harness rankings are not a property of the harness
  alone — the paper explicitly argues capability must be reported "at the model–harness configuration level".
- Sensitivity is asymmetric: weak models depend heavily on harness; strong models tolerate differences in prompting,
  tool interfaces, state management and recovery. Authors: stronger models "may reduce the need for prompt-level
  scaffolding and simple procedural guidance" but still need "permission boundaries, persistent state, interpretable
  traces, evidence records, and objective verification".
- Failure analysis frames the dominant failures as *execution alignment* (reasoning decoupled from tool feedback,
  workspace state, evidence, output contracts) — these are harness-structural, not model-specific prompt issues.

**Implications for our design.**
- Classify harness components along the paper's split: (a) *prompt-level scaffolding / procedural guidance* —
  model-bound, value shrinks with stronger models, likely to overfit; (b) *execution substrate* — output-contract
  validators, permission gates, persistent state/checkpoints, traces, evidence ledgers, verification hooks —
  model-agnostic and valuable for every model. Treat (b) as the stable "core" and (a) as a per-model overlay.
- Weaker/cheaper customer runtime models will show the biggest gains AND the biggest risk from harness mutations; the
  FDE review UI should flag which runtime model a mutation was validated on.
- The 36.4% contract/format + 11.1% artifact-commitment failures suggest the highest-ROI, most portable mutations are
  deterministic output-contract checks and "commit artifact" enforcement in control logic, not prose instructions.
- Customer tasks that are data/tool/workspace-heavy will be the most harness-sensitive (and so most model-sensitive);
  pure comms tasks less so — prioritize eval coverage accordingly.
- Eval records should key results by (model, harness_version) pair, never by harness version alone.

---

## 2. Self-Harness (arXiv 2606.09498)

**Citation.** Zhang H., Zhang S., Li, Zhang C., Chen, Zhang Y., Bai, Hu (Shanghai AI Lab).
"Self-Harness: Harnesses That Improve Themselves." arXiv:2606.09498 (v1 8 Jun 2026; read v3, 20 Aug 2026).
https://arxiv.org/abs/2606.09498
Read status: full text incl. appendices (31 pp.). Code-diff figures (Figs. 5, 6, 10b...) are images; their content is
known only through the captions/body text summarized below.

**Setup.**
- Loop (Alg. 1): (1) *Weakness Mining* — run fixed model M under harness h_t on held-in split; cluster failed traces by
  exact-match failure signature phi = (terminal verifier cause, causal status of agent behavior, abstract agent
  mechanism); rank clusters by support x actionability -> evidence bundle. (2) *Harness Proposal* — the SAME model M
  (no stronger external optimizer) proposes K materially distinct, minimal edits, each tied to one failure mechanism
  and one declared editable surface, with an audit record (target pattern, surface, expected effect, regression
  risk). Non-addressable clusters (capability limits, flaky tasks) are explicitly skipped. (3) *Proposal Validation* —
  accept iff Delta_in >= 0 AND Delta_ho >= 0 AND max > 0 (trade-offs rejected even if net positive); 2 repeats per
  candidate; compatible accepted edits are merged into h_{t+1}; rejected ones logged.
- Initial harness: minimal LangChain DeepAgents config (short system prompt, file/shell tools, AGENTS.md memory, empty
  subagents/skills, one-line bootstrap / execution / verification / failure-recovery instructions, disabled runtime
  control policy with max_recent_tool_errors / max_total_tool_messages). Only this harness-definition file is editable.
- Models: MiniMax M2.5, Qwen3.5-35B-A3B (local), GLM-5. Benchmarks: Terminal-Bench-2.0 (64-task subset), SWE-bench
  Verified (100: 67 in / 33 out), AppWorld (180: 90 train in / 90 test out, max 50 turns).

**Key numbers (Table 1; Pass %, initial -> final, held-in / held-out / overall).**

| Bench | Model | Held-in | Held-out | Overall |
|---|---|---|---|---|
| TB-2.0 | MiniMax M2.5 | 43.0 -> 50.0 | 40.5 -> 61.9 | 42.2 -> 53.9 (+28%) |
| TB-2.0 | Qwen3.5-35B-A3B | 15.1 -> 36.0 | 23.8 -> 38.1 | 18.0 -> 36.7 (+104%) |
| TB-2.0 | GLM-5 | 47.7 -> 57.0 | 42.9 -> 57.1 | 46.1 -> 57.0 (+24%) |
| SWE-V | MiniMax M2.5 | 51.5 -> 58.2 | 34.8 -> 40.9 | 46.0 -> 52.5 (+14%) |
| SWE-V | Qwen3.5-35B-A3B | 20.1 -> 42.5 | 18.2 -> 39.4 | 19.5 -> 41.5 (+113%) |
| SWE-V | GLM-5 | 53.7 -> 58.2 | 48.5 -> 50.0 | 52.0 -> 55.5 (+7%) |
| AppWorld | MiniMax M2.5 | 51.7 -> 62.8 | 45.6 -> 55.0 | 48.6 -> 58.9 (+21%) |
| AppWorld | Qwen3.5-35B-A3B | 25.0 -> 60.0 | 20.0 -> 44.4 | 22.5 -> 52.2 (+132%) |
| AppWorld | GLM-5 | 47.8 -> 92.2 | 41.1 -> 77.8 | 44.4 -> 85.0 (+91%) |

- Largest relative gain 132% (Qwen/AppWorld); largest absolute +40.6 pp (GLM-5/AppWorld). Weakest model (Qwen3.5-35B-A3B)
  gains most in relative terms on every benchmark — consistent with Harness-Bench's "weak models are harness-sensitive".
- Evolution trajectories are short: ~9–25 candidate evaluations per run, with many rejected candidates.

**Model-specific edits actually retained (the core evidence for co-adaptation).**
- TB-2.0 / MiniMax: create required output artifact early (bootstrap instruction rewritten); enable runtime policy that
  redirects after 50 tool calls; correct content tags for schema-valid tool content.
- TB-2.0 / Qwen: artifact-ensure subagent; dependency-verifier skill; precheck imports; "force a change" to break
  exploration loops; create missing files within 2 steps; tool-error-triggered middleware that re-injects a system
  prompt pointing at the missing artifact.
- TB-2.0 / GLM-5: write artifacts early + force cleanup; bound/stage/inspect external compute; persist PATH/env across
  shell sessions and verify; nudge from exploration to build/test.
- SWE-V: all three converge on *stronger verification* but via different structures — MiniMax: separate empty-diff
  detector + targeted local test enforcement; Qwen: patch-verifier subagent + pre-submission diff/test check (and a later
  "policy bloat -> targeted tests only" edit); GLM-5: dependency-aware FAIL_TO_PASS parse/install/rerun cycle folded into
  the verification instruction.
- AppWorld: all converge on *complete state retrieval (pagination) + correct completion semantics (action-only tasks
  return null)*, again via model-specific mechanisms (MiniMax: state-auditor subagent + temporal boundary; Qwen:
  prompt-level completion-contract and pagination guards; GLM-5: action-vs-information rule + exhaustive pagination
  before mutation).
- Authors' summary: "the retained mechanisms address benchmark-specific bottlenecks ... The concrete implementation of
  these mechanisms remains model-specific."

**What does / doesn't transfer and why.**
- IMPORTANT: Self-Harness runs **no cross-model transfer experiment** — every comparison is within-model. The claim
  that "effective harness design is inherently model-specific" is a premise (cited to Meta-Harness, AHE, Sclar et al.
  2024 on format sensitivity) plus qualitative evidence that different models evolved different edits. It does NOT
  show that MiniMax's harness hurts GLM-5.
- Transfer across *tasks* (held-in -> held-out, same model) is positive in all 9 cells. Caveat we should note: the
  held-out split is used by the promotion gate (Delta_ho >= 0 is an acceptance condition), so held-out numbers are
  selection-influenced, not a clean test set. Held-out sets are small (e.g. SWE-V 33 tasks).
- Qualitative pattern useful for us: the *failure mechanism / goal* of retained edits is shared across models within a
  benchmark (verify patches; exhaust pagination; commit artifacts early), while the *implementation surface*
  (prompt guard vs subagent vs middleware vs runtime limit vs specific thresholds like "50 tool calls", "within 2
  steps") is model-specific. This is the natural seam for a portable-intent / model-bound-implementation split.
- Authors' own limits: edits "may still reflect benchmark-specific failure patterns"; "higher-stakes harness changes
  would require stronger acceptance gates than pass-rate non-regression alone".

**Implications for our design.**
- Adopt their mutation record almost verbatim: each proposed mutation = {target failure cluster, edited surface,
  expected behavioral effect, regression risk, evidence}. This is exactly what an FDE needs to accept/edit/reject.
- Use failure signatures (verifier cause, causal status, mechanism) as the unit of "why" — and store the runtime model
  in the signature, because the mechanism a failure exposes is model-dependent (e.g. only Qwen needed loop-breakers).
- Represent each mutation in two layers: (i) *intent/invariant* ("must verify patch with targeted test before
  submit"; "must exhaust pagination before mutating state") — hypothesized portable; (ii) *realization* (prompt text,
  subagent, middleware hook, numeric thresholds) — model-bound. On model swap, keep (i), re-derive (ii).
- Acceptance gate should be non-regressive per split (their rule), plus our addition: re-validate on each runtime
  model the customer may use; a mutation accepted on model A is "unvalidated" on model B, not "accepted".
- Keep a clean, never-used-for-selection test split per customer; Self-Harness's held-out doubles as a gate.
- Self-proposal by the runtime model itself works even for mid-size open models (Qwen3.5-35B-A3B) — the proposer need
  not be a frontier model, which supports proposing per-model realizations cheaply.

---

## 3. HarnessDev (arXiv 2609.01437): cross-executor numbers, for reference

**Citation.** Wu, Zhang, Shi, et al. (ByteDance Seed / SUTD / Georgia Tech / M-A-P / TokenWave). "HarnessDev: Can LLMs Create
and Evolve Their Own Agent Harness?" arXiv:2609.01437, 1 Sep 2026. https://arxiv.org/abs/2609.01437
Read status: full text for the Creation, Evolution and executor-transfer sections (§4.2–4.3, Tables 3–7, §6). Appendices only skimmed.

**Setup (brief).** 6 creator LLMs (Opus 4.8, GPT-5.5, Gemini 3.1 Pro, DeepSeek V4 Pro, Qwen 3.7 Max, Seed 2.0 Pro) each build a harness
from a zero-scoring seed (Creation), then evolve it (Evolution). *Self-Eval*: the creator is also the executor. *Unified-Eval*:
Gemini 3.1 Pro executes every harness.

**Cross-model numbers.**
- Creation, Self-Eval to Unified-Eval (Gemini executor), avg score: Opus 67.8 -> 53.3; GPT-5.5 55.1 -> 44.8; DeepSeek 45.2 -> 48.8;
  Qwen 44.0 -> 52.8; Seed 22.8 -> 29.8. Harnesses from the strongest creators lose score when another model runs them, and
  harnesses from weaker creators gain score (their own executor was the bottleneck).
- Opus SWE-Pro: 69.3 -> 33.0 under Gemini (post-hoc clean mean 49.1 after dropping a collapsed replica). One Opus Code harness
  "nearly collapses under Gemini because it hard-codes a 120-step limit around the original executor". Opus Search harness:
  the duplicate-query rate goes from 10.1% to 88.2% once the executor changes, because its "deduplication, review, and
  termination rules are adapted to the original model". Qwen gains +17.6 (BrowseComp) and +12.9 (MLE-bench) under Gemini.
- Authors' conclusion: "capability transfers only when its prompts, tool protocol, budgets, and stopping rules remain compatible."
- Evolution, held-out SWE-Pro-630 (Table 6). Self-runtime lineages all improve slightly: Gemini +2.70, Opus +4.44, Qwen +1.43,
  DeepSeek +3.17, GPT-5.5 +3.81. The feedback-set gains were much larger (+3.0 to +13.9). In the fixed-Gemini-executor lineages
  (creator X evolves a harness that Gemini runs), results were Opus +2.70, Qwen -1.11, DeepSeek -2.38 and GPT-5.5 -10.32, even
  though feedback-set gains were positive (+1.1 to +9.7). So 3 of 4 regress on held-out.
- Other structural findings: 77.8% of failed Data tasks were attributed to harness defects. State/memory is the weakest
  component: only 1 of 18 Code harnesses implements checkpointing, and no checkpoint event appears in 26,679 trajectories. Of 108
  Code component instances, 18 never trigger. Across 64 evolution switches, 58 change control flow, 37 change tools, 4 change
  state, and 0 change a standalone verifier.
- Note: the fixed-Gemini Evolution result is really "creator != executor". It does not show "evolve on A, then swap to B".
  §6: "changing only the runtime binding can substantially move H0 and alter which harness changes are useful."

---

## 4. Other 2025–2026 work on cross-model portability

### 4a. PromptBridge: Cross-Model Prompt Transfer for LLMs (arXiv 2512.01420): read in full (main text and ablations)

**Citation.** Wang Y., Liu Q., Wang Z., Li Z., Wei W., Liu Y., Bao Y. (UC Santa Cruz / Accenture). arXiv:2512.01420, 1 Dec 2025.
https://arxiv.org/abs/2512.01420

**Setup.** The paper defines **Model Drifting**, the transfer gap Delta(Ms->Mt, T) = A(Mt, T, p*_Ms) - A(Mt, T, p*_Mt). MAP-RPE
(a reflective, island-based evolutionary prompt search, similar to AlphaEvolve and GEPA) finds a model-specific optimal prompt on
a small set of *alignment tasks* (synthetic code generation plus the CodeContests train split) for both the source and target
model. A GPT-5 "Mapping Extractor" then summarizes, in natural language, how source-optimal prompts systematically differ from
target-optimal prompts. At test time, a GPT-5 "Adapter" applies that summary to rewrite a source prompt for an unseen task,
zero-shot. Source model: GPT-4o (o4-mini for SWE-bench). Targets: o3, o4-mini, Llama-3.1-70B, Qwen3-32B, Gemma3-27B, GPT-4o.
Agent frameworks: mini-SWE-agent (SWE-bench Verified), Terminus (Terminal-Bench), MapCoder (4-agent), TravelPlanner (ReAct).

**Key numbers.**
- HumanEval drift: the GPT-5-optimal prompt gets 99.39% on GPT-5 but 68.70% on Llama-3.1-70B, whose own optimum is 79.47%
  (about 10.8 pt of drift). The Llama-optimal prompt gets 96.95% on GPT-5 (2.44 pt of drift). Drift is **asymmetric**: prompts
  tuned for strong models hurt weak models much more than the reverse. GPT-4o prompt to o3 gives 92.27% versus o3's achievable
  98.37%.
- Table 1, GPT-4o to o3, direct transfer vs PromptBridge: HumanEval 92.27 -> 97.15, MBPP 77.92 -> 80.44, APPS 32.67 -> 36.44,
  xCodeEval 66.04 -> 74.84, CodeContests 48.61 -> 56.36. GPT-4o to Llama-3.1-70B: 68.70 -> 79.88 (HumanEval), 65.57 -> 73.64 (MBPP).
  GEPA's transferred prompt *collapses* on Llama (35.98 HumanEval, 25.86 MBPP). This shows that an optimizer's output can be very
  model-bound.
- Agentic: relative to direct transfer, SWE-bench Verified +27.39% on o3, +15.79% on Llama-70B and +2.5% on GPT-4o (source o4-mini:
  38.60% default -> 42.20% optimized). Terminal-Bench +39.44% on o3 and +10.53% on o4-mini (source GPT-4o: 15% -> 18.75%). On o3,
  the directly transferred optimized prompt did **not beat the original default Terminus prompt**, so an optimization done on one
  model gave zero benefit on another. The GPT-5 generic "prompt optimizer" sometimes did worse than direct transfer (SWE-bench on
  GPT-4o: 9.40%).
- Multi-agent (MapCoder, HumanEval): gains are small and inconsistent. For example, GPT-4o to Llama global drift: direct 87.59,
  PromptBridge 87.80.
- Ablation: one-shot and few-shot ICL with example source/target prompt pairs is unstable (Llama HumanEval 41.26 one-shot). A
  distilled, explicit "transformation rule" works better than raw examples.
- The authors attribute drift to differences in training corpora, tokenization, **role tags and tool-call conventions** (for
  example Llama 3's `ipython` role) and alignment/RLHF criteria.

**What transfers.** Prompt *text* optimized for one model does not transfer reliably (sometimes 0 gain, sometimes large loss).
What does transfer is a *model-pair-level rewrite rule* (style, structure and verbosity preferences) learned on a few
calibration tasks. The rule even carried from the coding domain to TravelPlanner.

**Implications.** Prompt/context text is the most model-bound harness component. When the customer's runtime model changes,
the system should not re-run full evolution. It should run a cheap calibration step: re-optimize the prompt layer on about 5–50
calibration tasks per model (the ablation showed gains already at n=5), or apply a learned source-to-target rewrite rule, then
re-validate. Store a per-model "adapter note" alongside the harness.

### 4b. MemoHarness: Agent Harnesses That Learn from Experience (arXiv 2607.14159): read in full (main text)

**Citation.** Huang Y., Wang W., Bao H., et al. (Notre Dame / LMU / USC). arXiv:2607.14159, 14 Jul 2026.
https://arxiv.org/abs/2607.14159 (code: github.com/HowieHwong/MemoHarness)

**Setup.** The harness is a configuration over **six typed dimensions**: D1 context assembly, D2 tool/retrieval, D3 generation
(decoding), D4 orchestration topology, D5 memory, D6 output processing. A search over these dimensions starts from a minimal
harness, selects correctness-first with tokens as the tiebreaker, and uses a dual-layer experience bank (per-case diagnoses with
the primary failure dimension, plus distilled global patterns). At test time, the harness adapts per case via retrieval, with no
feedback. Search model: GPT-5.3-Codex.

**Key numbers.** Terminal-Bench: 0.722 -> 0.806, beating Codex, the strongest baseline, by +0.084. LiveCodeBench 0.900 -> 0.967.
FinanceAgent 0.600 -> 0.767. **Cross-model (Table 3)**: the frozen GPT-5.3-Codex-searched harness applied to 6 other models
improves all of them: Claude-Sonnet-4.6 0.530 -> 0.583, Gemini-3.1-Pro 0.611 -> 0.694, Qwen3.5-397B 0.444 -> 0.528,
GLM-5 0.500 -> 0.733, GPT-4.1 0.500 -> 0.538, DeepSeek-V3.2 0.333 -> 0.444. The mean gain is +0.098 (range +0.038 to +0.233).
Cross-suite transfer is "selective": for example, the Terminal-Bench harness gives +0.059 on SWE-Pro, and LawBench is mixed.

**Caveats.** The Terminal-Bench evaluation split is only **18 tasks** (cost table), so a 0.056 step is about one task, and the
authors themselves disclaim statistical robustness and component attribution. "Base" is each model's untuned base setting, not
a model-optimized harness. So this shows "better than a minimal harness on every model", not "as good as a harness evolved for
that model".

**Why it transfers (my reading).** The optimized object is a *structured configuration* of generic control decisions (add
retrieval, plan/execute/refine topology, schema-validating output handling, memory policy). It is not free-form, model-tuned
code with hard-coded budgets. The authors describe it as "a more portable execution policy for how an LLM should gather context,
invoke tools, manage intermediate state, and finalize outputs". The gain was smallest on the already-strong/calibrated GPT-4.1.

### 4c. Also relevant (abstract or targeted sections only, not read in full)
- **HarnessCompass** (arXiv 2608.01918, targeted read of Tables 1–3 and §§ on transfer). A "generalization gate" restricts
  evolution to task-agnostic edits. SWE-bench Verified with GPT-5.4: seed 51.8% -> 61.0% total (AHE 55.5%). The frozen
  GPT-5.4-evolved harness on Claude-Sonnet-4.6: 70.0% -> 73.8% total (68.0 -> 76.0 sample, 70.2 -> 73.6 held-out). Gains are uneven
  per repository: pytest -10.5 and sphinx -4.5 on Claude, where Claude's seed was already strong. The authors say "some mechanisms
  evolved for GPT-5.4 may be unnecessary for a stronger base model". The ungated evolution memory was full of instance-specific
  recipes (answer keys).
- **Harness Updating Is Not Harness Benefit** (arXiv 2605.30621, abstract only). *Harness-updating* ability is flat in base
  capability: Qwen3.5-9B's updates yield gains comparable to Claude Opus 4.6's. *Harness-benefit* is non-monotonic: weak models
  benefit little because they fail to activate or faithfully follow harness artifacts, mid-tier models benefit most, and strong
  models benefit less than mid-tier.
- Also surfaced but not read: Meta-Harness (2603.28052), Agentic Harness Engineering (2604.25850), "Rethinking the evaluation of
  harness evolution" (2607.12227), SEAGym (2606.17546), "The Scaffold Effect in Coding Agents" (2607.22585), MAPO (model-adaptive
  prompt optimization, Chen et al. 2024).

---

## 5. Synthesis for our design

**Evidence tally on "evolved harnesses don't transfer across runtime models".**
- Supporting: HarnessDev (Opus harness 69.3 -> 33.0 on SWE-Pro under Gemini; 3 of 4 fixed-executor evolution lineages regress on
  held-out; hard-coded step limits and dedup/termination rules are model-adapted). PromptBridge (optimized prompts give 0 gain or
  large losses on other models; GEPA prompt collapses on Llama). Harness-Bench (big model x harness interaction; weak models are
  very harness-sensitive). HarnessCompass per-repo regressions on Claude.
- Counter-evidence: MemoHarness (+0.098 mean across 6 other models) and HarnessCompass (+3.8 pt on Claude). Both constrain what
  evolution can produce, to structured dimensions or a task-agnostic gate. Self-Harness has *no* cross-model experiment, but its
  retained edits share goals across models and differ in realization.
- Reconciled view: co-adaptation is real, but it concentrates in specific components. Transfer is more likely when edits encode
  general execution invariants, and less likely when they encode model-calibrated text, budgets or thresholds. Direction matters
  too: harnesses tuned for strong models hurt weak models more than the reverse (PromptBridge asymmetry, HarnessDev
  Opus -> Gemini).

**Component classification (working hypothesis to test in our system).**

| Harness component | Portability | Evidence |
|---|---|---|
| Output-contract / schema validators, artifact-commit checks | Model-agnostic (high) | Harness-Bench failure taxonomy (36.4% contract, 11.1% artifact); Self-Harness edits for all 3 models converge on these |
| Verification gates (run targeted tests before submit, pagination-exhaustion checks) as *invariants* | Intent portable, realization model-bound | Self-Harness SWE-V/AppWorld: same goal, different mechanism per model |
| Permissions, security gate, state/checkpoint substrate, traces | Model-agnostic | Harness-Bench discussion; HarnessDev (state is underbuilt, not model-specific) |
| Retrieval / customer knowledge content (facts, policies, schemas) | Mostly model-agnostic | MemoHarness D1/D2 structured choices transferred |
| Tool definitions and schemas | Semantics portable, format model-bound | PromptBridge (role tags / tool-call conventions differ); Harness-Bench (weak models sensitive to tool interface) |
| System prompt / instruction wording / procedural nudges | Model-bound (low) | PromptBridge; Harness-Bench ("stronger models reduce need for prompt-level scaffolding") |
| Numeric budgets, step limits, loop-breaker thresholds, stopping/termination rules, dedup rules | Model-bound (lowest) | HarnessDev 120-step collapse, dup-query 10.1% -> 88.2%; Self-Harness "redirect after 50 tool calls" |
| Evals (task set, graders) | Model-agnostic, and they are the transfer test itself | All papers |

**Concrete design requirements.**
1. Key every eval result and every accepted mutation by `(runtime_model, harness_version)`. A mutation accepted on model A has
   status `unvalidated` on model B.
2. Each mutation record stores the Self-Harness audit fields (target failure signature, edited surface, expected effect,
   regression risk, evidence) plus a `portability_class` (invariant / realization / model-calibrated parameter). The FDE UI shows it.
3. Split every mutation into an *intent* (portable invariant, ideally enforced in code: validator, gate, hook) and a
   *realization* (prompt text, thresholds, subagent choice), which is re-derived per model. Prefer code-enforced invariants
   over prose, because they are the most portable.
4. Lint for executor-specific constants (step limits, tool-call caps, token budgets, retry counts) and require them to be
   per-model parameters, not literals.
5. On a model swap: run the eval suite on the new model with the current harness. Then (a) keep the invariants, (b) run a cheap
   per-model calibration of the prompt/threshold layer (PromptBridge suggests about 5–50 calibration tasks is enough), and (c) let
   the new runtime model self-propose realizations (Self-Harness shows mid-size models can do this). The FDE reviews the diff.
6. Use a non-regression acceptance rule (Self-Harness: no split may drop). Keep a never-used-for-selection test split per
   customer, because Self-Harness's "held-out" is also its gate and HarnessDev shows feedback-set gains shrink or reverse on truly
   held-out tasks.
7. Add a HarnessCompass-style "generalization gate": reject mutations that reference specific eval instances, because those are
   answer keys.
8. Expect the most harness sensitivity, and therefore the most model sensitivity, on data/tool/workspace-heavy customer
   workflows, and on weaker or cheaper runtime models.
