# Human-in-the-loop side of harness evolution — research notes
_Compiled 2026-09-26. Numbers copied from the papers/pages fetched; items marked [unverified] were not confirmed from primary source._

## 1. PRELUDE / CIPHER — learning from user edits
- Citation: Ge Gao, Alexey Taymanov, Eduardo Salinas, Paul Mineiro, Dipendra Misra. "Aligning LLM Agents by Learning Latent Preference from User Edits." NeurIPS 2024. https://arxiv.org/abs/2404.15269 ; code https://github.com/gao-g/prelude
- What: PRELUDE = interactive framework where agent drafts, user edits, agent infers a *natural-language latent preference* from the (draft, edit) pair and uses it in a prompt policy (no fine-tuning). CIPHER = LLM infers preference per context, stores it; at inference retrieves k nearest contexts' preferences and aggregates them.
- Cost signal = token-level Levenshtein edit distance between agent output and user-edited version (cumulative over rounds). Envs: summarization and email writing with GPT-4 simulated user.
- Numbers (cumulative edit distance, lower better):
  - Summarization: Oracle 6,573±1,451; No learning 48,269±957; ICL-edit-5 38,560; CoT-edit-5 40,747; CIPHER-5-MPNET 32,974±195.
  - Email: Oracle 1,851±243; No learning 31,103±900; ICL-edit-5 32,405; CoT-edit-5 24,292; CIPHER-5-BERT 8,391±3,038.
  - Preference-classification accuracy ~48% (summ.) / ~47% (email) vs random 20%/25%.
  - Token cost (x1e5 BPE): CIPHER 3.00 / 2.09 vs ICL-edit 8.00 / 12.12.
  - Human eval: CIPHER 73.3% win vs best baseline, 23.7% vs oracle. Large gap to oracle remains.
- Implication: Direct precedent for edit-distance-as-reward and for storing learned preferences as *readable, user-editable text* (maps to our harness diff). Differences: PRELUDE edits *outputs*, not the prompt/harness; user is simulated; no versioning, no rollback, no survival. We can adopt normalized edit distance between proposed mutation and FDE-accepted final mutation as a graded signal (0 = accept, small = light edit, ~1 = rewrite), and CIPHER-style "infer the FDE's latent rule from the edit" to update the proposer.

## 2. ReMe — "Remember Me, Refine Me" (VERIFIED EXISTS)
- Citation: Zouying Cao, Jiaji Deng, Li Yu, Weikang Zhou, Zhaoyang Liu, Bolin Ding, Hai Zhao. "Remember Me, Refine Me: A Dynamic Procedural Memory Framework for Experience-Driven Agent Evolution." Findings of ACL 2026. arXiv 2512.10696. https://aclanthology.org/2026.findings-acl.829/ ; code https://github.com/agentscope-ai/ReMe
- What: procedural memory with (1) multi-faceted distillation (success patterns, failure triggers, comparative insights), (2) context-adaptive reuse via scenario-aware indexing, (3) utility-based refinement: adds valid memories and *prunes outdated ones*. Fully automated, no human.
- Pruning rule (from arXiv HTML): an experience recalled >= alpha times whose average utility across recalls falls below beta is deleted; alpha=5, beta=0.5.
- Numbers (Avg@4 / Pass@4):
  - Qwen3-8B: no-mem BFCL-V3 40.33/59.55, AppWorld 14.97/32.85 -> ReMe 45.17/68.00, 24.70/42.06.
  - Qwen3-14B: no-mem 48.66/68.22, 22.57/41.07 -> ReMe 55.00/74.44, 34.32/52.98.
  - Qwen3-32B: no-mem 54.55/72.44, 27.23/50.59 -> ReMe 56.17/76.44, 42.02/63.49.
  - So 8B+ReMe (Avg@4 AppWorld 24.70, BFCL 45.17) vs 14B no-mem (22.57 / 48.66): beats 14B on AppWorld Avg@4 and on Pass@4 both; the "8B+ReMe > 14B memoryless" claim is from the abstract — check which metric/average it refers to before quoting.
  - Baselines 8B Avg@4: A-Mem 41.22 (BFCL) / 12.95 (AppWorld); LangMem 44.11 / 11.46.
  - Ablation (reported by fetch tool, verify table): deletion adds Pass@4 64.66 -> 68.00, Avg@4 45.00 -> 45.17.
- Implication: our "survival tracking" is a human-grounded analogue of ReMe's utility-based refinement: replace automatic utility with FDE decisions + downstream outcomes; use an alpha/beta style rule (min exposure count before retirement). Accurate to cite ReMe as prior work on pruning stale procedural knowledge; it does NOT involve human review or versioned harnesses.

## 3. Letta "Context Repositories" (VERIFIED EXISTS — blog post, not a paper)
- Citation: Letta, "Introducing Context Repositories: Git-based Memory for Coding Agents," blog, Feb 12 2026. https://www.letta.com/blog/context-repositories/
- What: Letta Code stores agent memory as files in a local git repo; every memory change is a commit with a message; subagents work in git worktrees and merge; "memory reflection" background process persists learnings; "memory defragmentation" skill splits/merges/restructures memory into ~15–25 focused files. Enabled via `/memfs enable`.
- Numbers: none beyond the "15–25 files" target. No benchmark.
- Not in the post: explicit stale-memory supersession policy, human approval of memory commits, survival metrics.
- Implication: closest industry precedent for *versioned* agent context (git commits = our harness versions). Our delta: the commit is proposed, then gated by a human FDE, and each version's survival/rollback is tracked as learning signal. Don't claim Letta prunes stale knowledge by utility — the post describes reorganization/dedup, not utility-based retirement.

## 4. ARIA — self-improving agent with human-expert guidance + timestamped, supersedable knowledge (closest single precedent)
- Citation: Yufei He, Ruoyu Li, Alex Chen, Yue Liu, Yulin Chen, Yuan Sui, Cheng Chen, Yi Zhu, Luca Luo, Frank Yang, Bryan Hooi. "Enabling Self-Improving Agents to Learn at Test Time With Human-In-The-Loop Guidance." EMNLP 2025 (per arXiv page). arXiv 2507.17131. https://arxiv.org/abs/2507.17131
- What: agent self-assesses uncertainty, asks human experts targeted questions (label / explanation / correction) under a query budget B, writes answers into a Knowledge Repository. Entries = (kid, K, ts_added, ts_validated, status, meta), status in {Valid, PotentiallyOutdated, Superseded}; contradicting new rule marks old one Superseded with superseded_by pointer; retrieval weights by status x exp(-lambda * age since validation) x relevance. Deployed on TikTok Pay customer due-diligence (>150M MAU).
- Numbers (TikTok Pay CDD, N=11,846, 156 positives): ARIA GPT-4o at B=1000 sensitivity 0.8910 / specificity 0.8026 vs Simple Uncertainty 0.8718/0.7853, RAG 0.8333/0.7462, Reflexion 0.7692/0.6902, Self-Refine 0.7244/0.6821, static GPT-4o 0.7051/0.6539. Budget curve sensitivity 0.8013 (B=50) -> 0.8333 (100) -> 0.8653 (500) -> 0.8910 (1000). Ablation B=100: full 0.8333/0.7423; labels-only 0.7949/0.7139; w/o conflict resolution 0.8012/0.7128. AHT: humans 12 min/case vs ARIA 0.13–0.41 min. CUAD legal B=2000: ARIA 0.6358 acc vs RAG 0.5735, static 0.4872.
- Implication: validates (a) rich human feedback > labels-only (explanations/corrections add ~4 pts sensitivity at B=100) — supports capturing FDE *edits + rationale*, not just accept/reject; (b) explicit supersession chain with pointers ≈ our version lineage. Differences: human answers questions about *domain rules*, doesn't review agent-proposed *harness mutations*; no rollback or downstream survival metric.

## 5. Agent-in-the-Loop (AITL) — Airbnb customer-support data flywheel
- Citation: Cen (Mia) Zhao et al. (Airbnb). "Agent-in-the-Loop: A Data Flywheel for Continuous Improvement in LLM-based Customer Support." EMNLP 2025 Industry Track. arXiv 2510.06674. https://arxiv.org/abs/2510.06674
- What: human support agents give four in-workflow feedback types: pairwise response preferences, adoption + rationale, knowledge relevance checks, missing-knowledge identification. Feeds retrieval/generation model updates.
- Numbers (production pilot): recall@75 +11.7%, precision@8 +14.8%, helpfulness +8.4%, agent adoption +4.5%; retraining cycle months -> weeks.
- Implication: "adoption" (did the human use the suggestion) is the customer-support analogue of FDE accept; rationale capture is valuable. But learning target is model/retriever retraining, not a versioned harness; no graded-edit signal or mutation survival.

## 6. Learning Selective LLM Autonomy from Copilot Feedback (enterprise CS)
- Citation: Nikita Borovkov, Elisei Rykov, Olga Tsymboi, Sergei Filimonov, Nikita Surnachev, Dmitry Bitman, Anatolii Potapov. "Learning Selective LLM Autonomy from Copilot Feedback in Enterprise Customer Support Workflows." arXiv 2604.23855 (2026). https://arxiv.org/abs/2604.23855 (venue/affiliation not stated on abs page)
- What: logs UI traces, runs in copilot mode where operators accept/reject action suggestions; trains action policy + critic that decides when to defer to human. Deployed in a BPM platform (~15,000 customers per experimental group).
- Numbers: 45% of sessions automated end-to-end; average handling time -39%; critic precision 74.68% vs 70.84% confidence baseline; selective automation within 2 weeks for a new process. 37.2% of rejections were operator preference / optional steps => binary accept/reject is noisy; authors state graded feedback would be preferable but not implemented. Drift: slice-level guardrails, auto-fallback to copilot-only when breached, rolling-window retraining.
- Implication: direct empirical motivation for our graded signal (accept > small edit > rewrite > reject) — binary signals conflate "wrong" with "stylistic preference". Their guardrail->fallback is analogous to our rollback. They learn weights, not an inspectable versioned harness.

## 7. Other items checked (brief)
- iPrOp: Interactive Prompt Optimization with a Human in the Loop, arXiv 2412.12644 — human picks among prompt candidates; not read in depth (numbers not extracted).
- SkillForge (SIGIR 2026 Industry): self-evolving skills for cloud technical support, 1,883 tickets / 3,737 tasks, claims to surpass manually curated expert knowledge. Abstract does not describe human approval of skill updates. arXiv 2604.08618.
- Evidence-in-the-Loop (arXiv 2607.18039): CS RAG pipeline where unresolved conversations go to humans who annotate evidence inside the workflow; abstract gives no numbers, no versioning/rollback detail.
- EvoUndo (arXiv 2608.28363): recoverability-constrained harness self-evolution; 197 capability-improving mutations failed recoverability verification across 600 unseen tasks; recovery ~99.3% in some strata. No human review. Relevant to our rollback design.
- StarHarness (arXiv 2608.24804): enterprise harness evolution, +20–35 pts after 4–12 "accepted changes" per environment; abstract doesn't describe human review — "accepted" appears to be an automatic gate [not verified in full text].
- FDE literature: only industry blogs (e.g., resolve.ai, Salesforce, multimodal.dev, Frontier AI substack). No peer-reviewed paper on forward-deployed engineering with AI found.

## Novelty check
Did NOT find any system that combines (1) human expert review (accept/edit/reject) of (2) agent-proposed, versioned harness/prompt mutations with (3) survival/rollback tracking of those versions as a learning signal. Nearest neighbors each cover part:
- PRELUDE/CIPHER: edit distance of human edits as signal — on outputs, simulated user, no versioning.
- ARIA: human expert corrections + supersedable timestamped knowledge — no mutation review, no survival.
- Copilot-feedback CS paper / AITL: accept/reject/adoption in live CS — binary, updates model weights.
- ReMe: utility-based pruning of procedural memory — automated.
- Letta Context Repositories / EvoUndo / harness-evolution papers: git-versioned or reversible self-modification — no human gate.
- Industry blog (futureagi.com) recommends "agent proposes, human disposes" with versioned prompts + rollback as practice, but it is a checklist, not an evaluated system.
Caveat: search was not exhaustive; claim as "to our knowledge".

## Design implications (summary)
1. Graded FDE signal: map accept=1.0, small edit, rewrite, reject=0 using normalized token edit distance between proposed diff and final committed diff (PRELUDE uses token Levenshtein). Copilot paper shows binary signals are noisy (37.2% of rejects were preference).
2. Capture rationale on edit/reject (ARIA: rich feedback > labels-only; AITL collects rationales). Run CIPHER-style inference of the FDE's latent rule from each edit and store it as readable text.
3. Survival tracking = human-grounded ReMe utility pruning (min exposures alpha before retiring; utility threshold beta) + ARIA-style Superseded status with superseded_by pointer.
4. Versioning via git-like commits (Letta) with guaranteed reversibility (EvoUndo); rollbacks are negative signal on the mutation and on the proposer's pattern.
