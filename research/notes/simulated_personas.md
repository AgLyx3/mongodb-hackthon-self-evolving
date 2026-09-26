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

### tau^tau-Bench / Hyper-tau-bench (Sierra, Sep 2026) [V] -- MOST DIRECTLY RELEVANT to "customer contact"
- Citation: "tau^tau-Bench: An Environment for End-To-End, Realistic Agent Construction."
  arXiv:2609.04611. https://arxiv.org/abs/2609.04611 ; blog
  https://sierra.ai/blog/hyper-t-bench-evaluating-agents-that-build-agents ;
  code https://github.com/sierra-research/hyper-tau-bench
- Setting: a developer agent builds a customer-service agent for a business (very close to FDE work).
  53 tasks; on "+client" tasks 20-25 requirements are moved OUT of the corpus and held only by an
  LLM-simulated client (busy operations manager, short plain replies).
- Knowledge boundary = a set of fact IDs in three buckets: held-only facts ("what_only_you_know"),
  conflicting facts ("records_in_conflict": client says which version is current), and checkable
  facts ("questions_you_can_settle": in records but easy to misread). The client system prompt is
  *rendered deterministically from the fact schema and embeds only the facts it may discuss, so
  nothing else can leak* (Appendix I) -> the scope is unit-testable.
- Behaviour rules: only answers what was asked, never volunteers neighbouring rules; refuses to
  recite policy that is in the records ("that is exactly what the records are for"); on developer
  hypotheses it CONFIRMS correct readings ("Yes, that's right") and sends incorrect ones back to the
  records WITHOUT supplying the correction.
- Numbers: developers asked the client at most 4 questions before shipping; builds that asked
  outscore those that never did by ~3x. Elicitation is measurable per fact ID.
- Borrow (customer contact): replace keyword table with a fact-ID registry {id, bucket, answer
  text, trigger paraphrases}; render the contact's prompt only from facts in its bucket; log which
  fact IDs were surfaced -> "elicitation recall" metric. Borrow (FDE): "confirm-if-right,
  redirect-to-evidence-if-wrong, never supply the correction".

### HiL-Bench (2026) [V]
- Citation: "HiL-Bench (Human-in-Loop Benchmark): Do Agents Know When to Ask for Help?"
  arXiv:2604.09408. https://arxiv.org/abs/2604.09408
- Mechanism: ask_human() is a frozen LLM (Llama-3.3-70B-Instruct) used ONLY as a semantic matcher
  between the agent question and a registry of blockers (type, gap description, exact resolution,
  diverse trigger questions). Match -> return the canned resolution; else the fixed string
  "irrelevant question". "Binary, reproducible signal ... without the confounds of free-form
  simulation." Resolution must not be inferable from anything else the agent can see.
- Metric: Ask-F1 = harmonic mean of question precision (relevant/total asked) and blocker recall;
  penalizes question spam.
- Validation: matcher 97% precision / 91% recall vs held-out human-annotated question-blocker
  pairs; tasks iterated until >=85% trigger-question recall.
- Borrow (customer contact): hybrid = LLM matcher + canned answers (fixes brittle keyword table,
  keeps determinism & no leakage). Report Ask-F1 so the agent can't farm the contact.
  Validate matcher on a small labelled set of paraphrased questions.

### SimulatorArena (Dou et al., Microsoft, EMNLP 2025) [V-abstract]
- Citation: arXiv:2510.05444. https://arxiv.org/abs/2510.05444 ; https://github.com/microsoft/SimulatorArena
- Mechanism: 909 annotated human-LLM conversations (math tutoring, document creation); evaluates
  simulators on (i) message-level realism vs humans and (ii) whether ratings produced via the
  simulator match human ratings of the assistant.
- Numbers: profile-conditioned simulators reach Spearman ~0.7 with human judgments on both tasks
  (search summary: up from ~0.61 / ~0.55 without profiles [S]).
- Borrow: validate the simulated FDE *extrinsically*: does ranking of proposer variants under the
  simulated FDE match ranking under a real FDE on a small set? Give the FDE a profile (expertise,
  strictness, what it knows) rather than a bare checker.

### Lost in Simulation (2026) [V]
- Citation: "Lost in Simulation: LLM-Simulated Users are Unreliable Proxies for Human Users in
  Agentic Evaluations." arXiv:2601.17087. https://arxiv.org/abs/2601.17087
- Study: ~40 participants per group, US (SAE/AAVE x 3 age bands), India, Kenya, Nigeria; 18
  tau-bench retail tasks.
- Numbers: ~9 pp swing in agent success just from changing user-sim model (Sonnet 3.7 vs 4.5);
  simulators underestimate on hardest tasks, overestimate on moderate ones; simulated users ask
  questions in 18.8% of turns vs 9.8% for humans; politeness markers 39.2% vs 19.9%; up to 19 pp
  gap SAE vs AAVE 55+.
- Borrow: run the eval under >=2 simulator configurations (e.g., strict vs lenient FDE, two
  LLMs) and report the spread; treat the simulator as a variable, not a constant.

### Beyond Cooperative Simulators (2026) [V]
- Citation: "Beyond Cooperative Simulators: Generating Realistic User Personas for Robust
  Evaluation of LLM Agents." arXiv:2605.12894. https://arxiv.org/abs/2605.12894
- Mechanism: default simulators are "overly cooperative, perfectly consistent, and highly
  forthcoming"; real users withhold until prompted, push back, are ambiguous, vary in patience.
  Personas along axes (terseness, skepticism, frustration, ambiguity) generated by an
  evolutionarily-searched Python generator scored for human-likeness (19 behavioural features) +
  coverage.
- Numbers: annotators judged persona-conditioned users human 80.4% vs 46.5% for default sims;
  +17% relative agent gain from training on diverse personas.
- Borrow: persona axes for the customer contact (terse / vague / occasionally wrong about their
  own process) and for the FDE (strict vs permissive, busy -> short reasons).

### Goal alignment / UGST (Mehri et al., 2025) [V-abstract]
- Citation: "Goal Alignment in LLM-Based User Simulators for Conversational AI." arXiv:2507.20152.
  https://arxiv.org/abs/2507.20152
- Mechanism: LLM user sims drift from their goals over multi-turn conversations; User Goal State
  Tracking keeps an explicit goal-progress state that conditions each response. Gains on
  MultiWOZ 2.4 and tau-bench (exact numbers not extracted [U]).
- Borrow: keep FDE/contact state explicit (what has been revealed, which facts confirmed) in
  code, not in the LLM's context.

### Persona drift (Li et al., 2024) [S]
- Citation: "Measuring and Controlling Persona Drift in Language Model Dialogs" (later titled
  "...Instruction (In)Stability..."). arXiv:2402.10962. https://arxiv.org/abs/2402.10962
- Finding: significant persona drift within 8 rounds (LLaMA2-chat-70B), attributed to attention
  decay. Borrow: re-render the persona prompt each turn / stateless per-proposal reviews.

### DuetSim (Luo et al., COLING 2024) [V-abstract]
- arXiv:2405.13028. Two LLMs per user turn: generator + verifier that checks goal constraints.
- Borrow: generator phrases the FDE's feedback; a deterministic verifier (not an LLM) checks the
  feedback contains no answer-key tokens and is consistent with the decided verdict.

### IDRBench (Feng et al., 2026) [V-abstract; leak pipeline details U]
- arXiv:2601.06676. Interaction helped in 74.4% of cases, hurt in 19.9%; avg +6.39 pts; measures
  interaction cost (turns, tokens). Search snippet [S] describes a leak-control pipeline for the
  simulated user: explicit "don't mention" instruction + deterministic string matching + LLM
  leak-checker + regenerate. Could not confirm this pipeline is from IDRBench specifically [U].
- Borrow: the 3-layer leak guard (instruction, string match on answer-key tokens, LLM judge).

### HAS-Bench (2026) [V-abstract only; details U]
- arXiv:2607.04329. Humans and agents as first-class participants with roles/permissions;
  configurable human agency, channel and persona policies. "Human participation can
  substantially improve task completion ... but the gains depend on when, how, and by whom."
  Specific noise/error-rate settings not verified.

### Non-Collaborative User Simulators for Tool Agents (Shim et al., 2025) [V-abstract]
- arXiv:2509.23124. https://arxiv.org/abs/2509.23124 ; code https://github.com/holi-lab/NCUser
- Four non-collaborative modes layered on a simulator that still "reliably deliver[s] all intents and
  information necessary": requesting unavailable services, tangents, impatience, incomplete
  utterances. Significant agent degradation on MultiWOZ and tau-bench.
- Borrow (customer contact): add modes like "asks for something out of scope", "half-answers,
  needs follow-up" -- but keep a guarantee that every planted fact is reachable by a good question.

---

## 3. Realism: noise, inconsistency, human-reviewer base rates

- Real reviewers of agent output are noisy and often give no reason. "Why Are Agentic Pull
  Requests Merged or Rejected?" (MSR 2026) arXiv:2605.22534 [V-abstract]: 11k+ agentic PRs,
  717 manually reviewed; only 35.7% of rejections were genuine agent failures, 31.2% workflow
  constraints, 33.1% no clear rationale; 15.4% of merges needed reviewer intervention (feedback or
  direct commits). Search snippet [S]: agentic PR acceptance 83.77% vs 91.01% human-authored.
  Borrow: a realistic FDE rejects some correct proposals for non-technical reasons and sometimes
  gives no reason; ~1/3 of rejections unexplained is a real-world ceiling, so reasons should not be
  treated as always-present/always-informative.
- Expert triage disagreement (analogous domain: human triage). ESI systematic review [S]:
  inter-rater kappa ~0.75, under-triage 10.7%, over-triage 6.2%
  (https://pmc.ncbi.nlm.nih.gov/articles/PMC12966911/). International multicenter study of 87
  ESI-trained nurses [S, PubMed blocked by captcha]: mean accuracy 59.2%, alpha = .730
  (https://pubmed.ncbi.nlm.nih.gov/29174836/). Borrow: even trained experts disagree on ~10-25%
  of triage calls -> a 5-15% FDE error/disagreement rate is a defensible noise setting; report
  results at 0% and at a realistic noise rate.
- "Aligning to Illusions: Choice Blindness in Human and AI Feedback" arXiv:2603.08412 [V-abstract]:
  91% of surreptitiously swapped preferences undetected by humans; reward signal degrades only
  after 1/6-1/3 of labels are corrupted, while eval metrics barely move. Borrow: humans can be
  talked into accepting what's put in front of them -> model an FDE acceptance bias toward
  confidently-worded proposals (sycophancy of the reviewer), and check the agent doesn't exploit it.
- "Don't Blindly Trust It" arXiv:2606.21409 [V-abstract]: misleading feedback drops HotpotQA F1
  to 4.7 vs 22.3 no-feedback vs 44.8 clean. "Clean-tool gains can overstate tool value" ->
  include matched no-feedback control. Borrow: run (a) no-FDE, (b) noisy FDE, (c) clean FDE;
  the headline should be the gap, not (c) alone.
- Simulated users are too polite / ask too many questions (Lost in Simulation: 18.8% vs 9.8%
  question turns; politeness 39.2% vs 19.9%) and too forthcoming (Beyond Cooperative Simulators).
- Persona drift within ~8 turns (Li et al. 2024) -> keep reviews stateless per proposal.

## 4. Validating the simulator (what papers actually do)

| Method | Source | Numbers |
|---|---|---|
| Manual annotation of simulator turns, critical vs benign errors | tau2-bench | 16-47% error, 6-13% critical |
| Side-by-side human vs sim feedback, downstream outcome equality | MINT | 91.2% as helpful; 92% indistinguishable; 32.7 vs 33.6% |
| Canary-phrase leak detection | ConvCodeWorld | leak 2.5% (GPT-4o) to 51.1% (GPT-4-0613) |
| Matcher precision/recall on held-out human-labelled Q-A pairs | HiL-Bench | 97% P / 91% R |
| Extrinsic: correlation of sim-based ratings with human ratings | SimulatorArena | Spearman ~0.7 |
| Real-user study, success-rate calibration, multi-simulator spread | Lost in Simulation | 9 pp spread |
| Blinded "is this a human?" test | Beyond Cooperative Simulators | 80.4% vs 46.5% |
| Deterministic prompt rendering from fact schema -> unit tests of scope | tau^tau-Bench | n/a |
| Static cached feedback vs live, rank correlation | ConvCodeBench | Spearman 0.82-0.99 |

Failure modes named in the literature: over-cooperation / over-forthcoming, leaking ground truth,
hallucinating facts outside the instruction, goal drift, persona drift, role reversal (user starts
solving), sycophancy / politeness inflation, demographic bias, model-dependence of results.

## 5. Deterministic vs LLM vs hybrid

- Deterministic (our current FDE, HiL-Bench canned answers, tau^tau prompt rendering): reproducible,
  free, unit-testable, zero hallucination -- but if it holds the answer key and is allowed to
  *output* it, it leaks perfectly (our bug). Brittle to paraphrase (our keyword table).
- LLM (MINT, ColBench, tau-bench): natural, handles paraphrase; costs money, leaks at 2.5-51%
  depending on model (ConvCodeWorld), errs at 16-47% (tau2), drifts.
- Hybrid is the consensus direction: decisions + knowledge boundary in code, LLM only for
  (a) matching the question to a fact ID (HiL-Bench) and/or (b) phrasing (DuetSim-like
  generator + verifier). tau2-bench: moving user behaviour into structured tools cut sim errors
  from ~40-47% to 16%.
- Cost: ConvCodeWorld LLM feedback ~1.5% of human annotation cost; caching feedback preserves
  rankings (Spearman 0.82-0.99). HiL-Bench uses a 70B open model as matcher -> cheap.
- Trust or Escalate (Jung, Brahman, Choi, 2024; arXiv:2407.18370) [V-abstract]: selective
  evaluation -- judge abstains when not confident and escalates; cascade cheap->strong model;
  >80% human agreement guarantee with Mistral-7B on Chatbot Arena. Borrow: the simulated FDE can
  abstain ("need more evidence") instead of always deciding.

## 6. Graded feedback without supplying the answer

- tau^tau-Bench client: confirm correct hypotheses; redirect incorrect ones to the records
  WITHOUT the correction.
- ColBench: describe differences in words; never write the artifact.
- MINT: "patient teacher", suggestions not solutions; note GT-in-feedback can hurt decision tasks.
- ConvCodeWorld: graded feedback levels (novice = verbalized execution/test result; expert = sees
  reference). A novice-level analogue for us = "here are the cases your rule got wrong" (execution
  feedback) with no rule text.
- Tutor literature (Socratic hinting; "Evaluating Answer Leakage Robustness of LLM Tutors against
  Adversarial Student Attacks", Zhao, Knezevic, Kaser, ACL 2026, arXiv:2604.18660 [V-abstract]):
  answer leakage under adversarial/persuasive probing is a measurable failure; simple defences
  reduce it. Borrow: red-team the FDE with a proposer that tries to extract thresholds via
  repeated narrow proposals (binary search) -- cap rounds / cost each edit.
- Classic theory (not verified this session, well known): Angluin 1987, "Learning regular sets
  from queries and counterexamples" (Information and Computation 75(2)) -- the "minimally adequate
  teacher" answers equivalence queries with a single COUNTEREXAMPLE, not the target. This is the
  cleanest formal model for a hint-only FDE: reply to a proposed scope with one misclassified case.
- HiL-Bench Ask-F1: penalize question/edit spam so hint-farming isn't free.

---

## Ranked design changes for our simulated FDE (and customer contact)

1. **Stop emitting the answer key: replace "edit to exact scope" with counterexample-only
   feedback.** On too-broad: return 1-2 cases the rule wrongly includes (from the TRAIN split
   only) + direction tag ("too broad"); on too-narrow: 1-2 missed cases. Never return thresholds,
   field names, or rule text. (Angluin MAT; tau^tau "redirect without correction"; ColBench "may
   describe, may not write"; ConvCodeWorld novice-level feedback.) Keep "accept" and "reject with
   reason" as-is; "edit" becomes "the FDE's own edit" only from partial knowledge (see 2).
2. **Partial knowledge.** Give the FDE a lossy view: intent statements ("large enterprise outages
   should page on-call") + a sample of labelled cases, not the exact planted predicate. Any FDE
   edit is then computed from what it knows and can be wrong/approximate (e.g., rounds thresholds
   to "about 500"). (tau2 known/unknown; tau-bench intent-not-policy; ColBench caveat.)
3. **Leak guard + canary metric.** Plant unique tokens (exact threshold values, internal rule IDs)
   in the answer key; any FDE/contact output containing them is flagged and counted; report leak
   rate. If using an LLM phraser, run string-match + LLM leak-check + regenerate.
   (ConvCodeWorld canary; IDRBench-style pipeline [S].)
4. **Add a "need more evidence" / abstain action and an interaction budget.** FDE can respond
   "show me cases where this fires on X" instead of deciding; each FDE round costs budget; score
   Ask/Edit-F1 or rounds-to-accept. (Trust or Escalate; HiL-Bench Ask-F1; ColBench 10-round cap;
   IDRBench interaction cost.)
5. **Calibrated noise.** Wrong verdict rate ~5-15% (triage experts disagree 10-25%; kappa ~0.75),
   ~1/3 of rejections with no/unhelpful reason (agentic-PR study), occasional non-technical
   rejections ("not now"), mild acceptance bias for confident proposals. Seeded, so reproducible.
   Report at noise 0 and realistic noise. (MSR 2026; ESI studies; Choice Blindness.)
6. **Report the reviewer-strength ladder, not one number.** Run: no FDE / counterexample-only FDE /
   partial-knowledge FDE / oracle FDE (current). The oracle row is an upper bound; the gap between
   rows shows how much the reviewer carries. Score on held-out cases the FDE never commented on.
   (ConvCodeWorld factorial feedback; "Don't Blindly Trust It" matched controls; MINT GT ablation.)
7. **Customer contact = fact-ID registry + LLM matcher, reactive only.** Render contact prompt
   from facts it may discuss (held-only / conflicting / checkable buckets); unmatched ->
   "I don't know / that's in the runbook"; confirm correct hypotheses, don't correct wrong ones;
   log surfaced fact IDs -> elicitation recall; add terse/vague persona modes that never block a
   well-asked question. (tau^tau-Bench; HiL-Bench; tau2; Non-Collaborative sims.)
8. **Validate the simulators.** (a) Unit-test that the rendered prompts contain no out-of-scope
   facts; (b) hand-annotate ~50 FDE/contact turns for critical errors & leaks (tau2 style); (c) if a
   real FDE is available, 10-20 proposal side-by-side and check rank agreement of proposer variants
   (MINT, SimulatorArena); (d) run under >=2 simulator configs and report spread (Lost in Simulation).
