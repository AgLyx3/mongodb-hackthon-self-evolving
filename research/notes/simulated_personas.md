# Simulating human participants (FDE reviewer, customer contact) in agent evaluation

Research notes, compiled 2026-09-26. Problem: our simulated FDE holds the full answer key and, on
too-broad/too-narrow proposals, edits them to the EXACT ground-truth scope -> injected thresholds
the agent never discovered -> 100% accuracy is an artifact. The simulated customer contact answers
from a keyword table.

Verification legend: [V] = read primary source (arXiv HTML/abstract) this session;
[S] = seen only via search snippet / secondary summary; [U] = could not verify.

---

## 1. User / persona simulators in agent benchmarks

### tau-bench (Yao et al., 2024) [V-abstract, S-details]
- Citation: Yao, Shinn, Razavi, Narasimhan. "tau-bench: A Benchmark for Tool-Agent-User Interaction
  in Real-World Domains." arXiv:2406.12045. https://arxiv.org/abs/2406.12045
- Mechanism: LLM user simulator gets a natural-language *instruction* (identity, goal, fallback
  preference, personality e.g. "You are concise"). The agent gets the policy doc + tools. The
  simulator never sees the policy or the DB, only its own goal; ground truth is the final DB state
  (checked deterministically), NOT anything the simulator says. Knowledge asymmetry: user knows the
  *what* (its goal), agent must figure out the *how* (policy/tools).
- Numbers: gpt-4o <50% success; pass^8 <25% in retail -> motivates repeated trials (pass^k).
- Borrow: separate "what the reviewer wants" (goal/intent in natural language) from "how it's
  scored" (deterministic check on final harness state). The FDE should hold *intent*, not the
  answer-key rule; the score comes from the held-out eval, not from the FDE's edits.

### tau2-bench (Barres et al., 2025) [V]
- Citation: "tau^2-Bench: Evaluating Conversational Agents in a Dual-Control Environment."
  arXiv:2506.07982. https://arxiv.org/abs/2506.07982 ; code https://github.com/sierra-research/tau2-bench
- Mechanism: user instructions split into "known info" vs "unknown info"; simulator told to
  "never make up or hallucinate information not provided in the scenario instructions".
  User can only call a tool if the agent requested it (reactive only); user tools return only
  human-readable output (complexity asymmetry: user can observe/act but not plan/solve).
- Numbers: manual annotation of simulator errors: retail 40% total / 12% task-critical,
  airline 47% / 13%, telecom 16% / 6%. Constraining via tools + structured action space cut
  simulator errors ~3x. GPT-4.1 pass@1 drops to ~34% in dual-control telecom.
- Borrow: (a) explicit known/unknown lists per customer-contact persona; unknown -> "I don't know,
  I'd have to check with ops". (b) "reactive only": contact answers only what was asked, never
  volunteers the rule. (c) audit a sample of simulator turns and report simulator error rate
  (task-critical vs benign) alongside agent scores.

### ColBench / SWEET-RL (Zhou et al., Meta, 2025) [V]
- Citation: "SWEET-RL: Training Multi-Turn LLM Agents on Collaborative Reasoning Tasks."
  arXiv:2503.15478. https://arxiv.org/abs/2503.15478 ; https://github.com/facebookresearch/sweet_rl
- Mechanism: LLM human-simulator holds a reference artifact (<=50-line code / reference HTML);
  it "will provide a brief explanation in natural language to each clarification question based on
  the reference code ... but it will not write code". Frontend: describes visual *differences*
  between agent render and reference. Max 10 rounds. Asymmetric actor-critic: only the critic
  (training-time) sees hidden info.
- Caveats: authors admit a real collaborator "might only have a general idea"; no real-human
  validation of the simulator reported.
- Borrow: "may describe, may not write" -- the FDE may describe the difference between the
  proposal and what it wants (in words / examples), but must not emit the rule text or thresholds.
  Interaction budget (N rounds) so hint-farming is bounded and costed.

### MINT (Wang et al., ICLR 2024) [V via ar5iv]
- Citation: "MINT: Evaluating LLMs in Multi-turn Interaction with Tools and Language Feedback."
  arXiv:2309.10691. https://arxiv.org/abs/2309.10691
- Mechanism: GPT-4 plays "a patient teacher who provides useful suggestions" without solving.
  Ground-truth may be given to the feedback generator.
- Numbers: human eval -- 91.2% of GPT-4 feedback judged as helpful or better than human feedback;
  indistinguishable from human in 92%; downstream success 33.6% (GPT-4 fb) vs 32.7% (human fb).
  Adding ground truth to the feedback generator helped reasoning/code but *hurt* decision-making
  (-8.95%). Feedback-giving ability is orthogonal to task-solving ability.
- Borrow: validate the simulated FDE by a small human-vs-simulator side-by-side on the same
  proposals (does the agent reach the same outcome with either?). Ground truth in the reviewer
  is a knob, not a default -- run an ablation "reviewer with/without answer key".

### ConvCodeWorld / ConvCodeBench (Han et al., ICLR 2025) [V]
- Citation: "ConvCodeWorld: Benchmarking Conversational Code Generation in Reproducible Feedback
  Environments." arXiv:2502.19852. https://arxiv.org/abs/2502.19852
- Mechanism: feedback levels as a factorial design: compilation (always), execution (partial vs
  full test coverage), verbal (novice = verbalized exec output; expert = GPT-4o sees reference
  code). 9 combinations. Leakage detected with a CANARY: the prompt calls the reference
  "ground truth code"; if that phrase appears in feedback, it counts as leakage.
- Numbers: canary leakage GPT-4o 2.5%, GPT-4-Turbo 31.4%, GPT-4-0613 51.1%. With expert feedback,
  DeepSeek-Coder-6.7B (82.8) beat GPT-4o single-turn (82.3) -> expert feedback can dominate the
  score (exactly our 100% problem). Cached-feedback static version correlates with live
  (Spearman 0.82-0.99). LLM feedback ~1.5% of human-annotator cost ($215 vs ~$14,792).
- Borrow: (a) report results across reviewer *levels* (novice / partial-key / full-key) instead of
  one number; the gap = how much the reviewer is carrying. (b) canary/leak detector: plant unique
  tokens in the answer key (exact thresholds, rule IDs) and flag any reviewer output containing
  them. (c) cache reviewer responses for reproducibility.

