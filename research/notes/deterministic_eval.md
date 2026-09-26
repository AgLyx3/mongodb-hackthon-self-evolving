# Prior art: deterministic evaluation for a typed, time-stamped decision benchmark

Researched 2026-09-26. Every number below was copied from the source text. "Abstract only"
means only the arXiv abstract was read, not the full paper. Numbers in core items were
checked against the raw HTML/PDF text, not just a summary.

## 1. Slot filling / dialogue state tracking (typed slots, exact-match scoring)

**Schema-Guided Dialogue (SGD), Rastogi et al. 2019** [S1] (full text read)
- What: "over 16000 dialogues in the training set spanning 26 services belonging to 16
  domains"; "the evaluation sets contain unseen services and domains". Each service gives a
  schema (slots + intents with natural-language descriptions), and a single model reads the
  schema as input so it can handle services it never saw in training.
- Metrics: Active Intent Acc, Requested Slot F1, Average Goal Accuracy (per-slot), and Joint
  Goal Accuracy ("average accuracy of predicting all slot assignments for a turn correctly";
  fuzzy match for non-categorical slots).
- Numbers (Table 4, test): SGD-S (trained on single-domain only) Avg GA 0.684 / Joint GA
  0.356; SGD-All Avg GA 0.560 / Joint GA 0.254. The model "performs better on seen services
  compared to unseen ones", which they attribute to "a significantly higher OOV rate for slot
  values of unseen services". They also note that "a low joint goal accuracy and high
  average goal accuracy ... indicates a possible skew between the performance of different
  slots."
- Borrow: a per-customer schema with slot descriptions as model input, plus held-out
  customers that never appear in dev (their unseen services). Report per-slot and joint
  metrics side by side, because the gap is diagnostic.
- Avoid: fuzzy matching. Our slots are typed, so keep exact match and normalize values in
  the spec (units, enums).

**MultiWOZ 2.4, Ye et al. (SIGDIAL 2022)** [S2] (README table read; paper PDF did not parse)
- What: "carefully rectified (almost) all the annotation errors in the validation set and
  test set", leaving the training set untouched.
- Numbers, JGA on MultiWOZ 2.1 vs 2.4: TRADE 45.60% vs 55.05%, SUMBT 49.01% vs 61.86%, STAR
  56.36% vs 73.62%, TripPy 55.18% vs 64.75%, D3ST (XXL) 57.8% vs 75.90%.
- Lesson: label noise alone moved JGA by about 10 to 18 points. Because our corpus is
  generated from a typed spec, gold labels are correct by construction. That is our main
  structural advantage over human-annotated DST. Add a validator that proves every gold
  value is derivable from the cited artifacts under the grounding rules.

**Relative slot accuracy, Kim et al. 2022** [S3] (abstract only)
- Claim: JGA and slot accuracy "have a critical limitation when evaluating belief states
  accumulated as the dialogue proceeds". They propose relative slot accuracy, which "does not
  depend on the number of predefined slots", and "encourages not solely the reporting of
  joint goal accuracy".
- Borrow: our state accumulates in the same way (a slot committed early and wrong keeps
  poisoning every later day). Score per slot on the clock, not only "whole record correct
  at day N".

## 2. Deterministic vs LLM user simulators and judges

**Agenda-based user simulation, Schatzmann et al. NAACL 2007** [S4] (full text read)
- The user state is S = (A, G) with goal G = (C, R): constraints C plus requests R. The
  agenda A is a stack of pending dialogue acts. Act selection is "a Dirac delta function"
  that pops the top n items. Clean-up of duplicate or satisfied requests "is a deterministic
  procedure". The only stochastic parts are n (user initiative) and small handcrafted push
  and goal-update probabilities.
- Result: even with hand-set parameters, the policy trained on the simulator reached "145 out
  of 160 dialogues (90.6%)" success with 40 real human subjects.
- Borrow: our oracle is a degenerate agenda simulator. Its goal is the gold record, and its
  requests are the client-held slots. Make it fully deterministic by fixing n = 1 and
  removing randomness. A fixed goal with rule-based responses was enough to train a policy
  that transferred to real users.

**tau-bench, Yao et al. 2024** [S5] (full text read)
- Setup: the user is played by an LLM ("gpt-4-0613"). Reward r = r_action x r_output in {0,1}:
  the final DB must be "identical to the unique ground truth outcome database", and
  responses must contain required outputs. Instructions are written so there is "only one
  possible outcome under the domain policy".
- Metric: pass^k = E_task[C(c,k)/C(n,k)], "the chance that all k i.i.d. task trials are
  successful".
- Numbers: gpt-4o pass^1 61.2 (retail) and 35.2 (airline). Pass^8 on retail drops "as low as
  ~25%". Without the policy in the prompt, gpt-4o airline falls from 33.2 to 10.8.
- The paper itself lists simulator limitations: typos or ambiguity in instructions, missing
  domain knowledge, and the simulator LM's "limited capacity at reasoning, calculation,
  long-context memorization".
- Borrow: grade by comparing end state (our final record) against gold, with a unique gold
  by construction, and report pass^k over seeds. Avoid the LLM user, which the next two
  sources show is a real noise source.

**tau2-bench, Barres et al. 2025** [S6] (full text read)
- Table 2, user-simulator error audit (critical = prevents task completion):
  airline 100 convs: 13 critical (13%), 34 benign, 47 total (47%). Retail 50: 6 (12%)
  critical, 20 (40%) total. Telecom 50: 3 (6%) critical, 8 (16%) total.
- The authors credit telecom's lower rate to a "structured interface and clear action space".
  In telecom, "only assertion functions are used to evaluate task success".
- Moving from no-user to dual-control costs 18% pass^1 for gpt-4.1 and 25% for o4-mini.
- Lesson: constraining the simulator with tools and state cut its error rate roughly 3x,
  and a scripted oracle takes this to 0 by construction. The 12 to 13% critical error rate
  in retail and airline is a floor on label noise that we avoid.

**Lost in Simulation, 2026** [S7] (abstract only)
- On tau-Bench retail: "agent success rates varying up to 9 percentage points across
  different user LLMs". Simulated users show "systematic miscalibration, underestimating
  agent performance on challenging tasks and overestimating it on moderately difficult ones".
- For us: swapping the simulator LLM alone can move scores by up to 9 points. Any agent gain
  smaller than that would be confounded with simulator choice. That is a strong argument for
  the scripted oracle.

**SimulatorArena, Dou et al. EMNLP 2025** [S8] (abstract only)
- The best profile-conditioned simulators reach "Spearman's rho of 0.7" against human judgments
  (909 annotated conversations). Even the best LLM simulator is correlated with humans, not
  a replacement for them.

**Rating Roulette, 2025** [S9] (abstract only)
- "LLM judges have low intra-rater reliability in their assigned scores across different
  runs ... almost arbitrary in the worst case." This supports the no-LLM-judge rule. I did
  not verify any numeric flip rates, so I cite none.

## 3. Knowledge conflict, temporal update, stale evidence

**ConflictBank, Su et al. 2024** [S10] (full text read)
- "7,453,853 claim-evidence pairs and 553,117 QA pairs". Conflict causes: misinformation,
  temporal ("clash between new and outdated information"), semantic.
- Metric: memorization ratio MR = OAR/(OAR+CAR). "All models exhibit memorization ratios below
  50%". For LLaMA2-70B, MR is 7.77% (temporal) and 3.73% (semantic) vs 9.45%
  (misinformation).
- With two conflicting evidences, models show "strong confirmation bias", and "models are
  susceptible to the order of evidence, with larger models tending to favor later pieces".
- Borrow/avoid: an agent can look good on "latest wins" just by preferring the item seen
  last. Decorrelate presentation order from effective date: include late-arriving artifacts
  that carry an older effective date, and backdated corrections.

**CONFLICTS ("DRAGged into Conflicts"), Cattan et al. 2025** [S11] (full text read)
- Taxonomy with expected behavior per type: no conflict, complementary, conflicting
  opinions, outdated information ("Freshness": "prioritize the up-to-date information"),
  misinformation. Counts: 161 / 115 / 115 / 62 / 5, total 458.
- Borrow: tie each conflict type to one required action, as in our rules (newer effective
  date: adopt; same-tier unresolved: escalate; lower-tier source: ignore). Label each seeded
  conflict in the spec with its type so rollbacks can be broken down by type.

**FRESCO, An et al. 2026** [S12] (full text read)
- Pairs recency-seeking queries with historical Wikipedia revisions. "Obsolete Ratio" is the
  share of wrongly-top-ranked negatives that are factually outdated. It "remains high for
  nearly all re-rankers (84%-98%)", showing "a strong bias toward older, semantically rich
  documents". Instruction optimization gives "gains of up to 27% on Evolving Knowledge tasks".
- Directly relevant to our Atlas Vector Search retrieval: semantic similarity will surface
  the stale-but-verbose KB page. Our stale-trap metric is an Obsolete Ratio at the
  decision level. Consider adding effective date as a filter or rerank feature.

**HoH, 2025** [S13] (abstract only): outdated information "substantially reduces response
accuracy" and "can mislead models into generating potentially harmful outputs, even when
current information is available". **FreshQA, Vu et al. 2023** [S14] (abstract only):
"all models ... struggle on questions that involve fast-changing knowledge". Their
"two-mode evaluation" scores correctness and hallucination separately, which is analogous to
our split between correct and silent errors.

## 4. Ask vs act, abstention, cost of asking

**AbstentionBench, 2025** [S15] (abstract only): 20 datasets, including "underspecification"
and "outdated information". "Reasoning fine-tuning degrades abstention (by 24% on
average)", and "scaling models is of little use". Implication: an escalate-on-conflict rule
will not emerge from a stronger model alone and has to be measured explicitly.

**SAGE-Agent / ClarifyBench, 2025** [S16] (abstract only): it scores clarifying questions by
Expected Value of Perfect Information over tool parameters, "balanced against aspect-based
cost modeling". Results: "7-39% higher coverage on ambiguous tasks while reducing
clarification questions by 1.5-2.7x", and When2Call accuracy up from 36.5% to 65.2% (3B).
Borrow: the questions go to typed slots, not free text, which matches our ask(slot). Report
both coverage and question count (our reviewer units).

**Calibrate-Then-Act, 2026** [S17] (abstract only): frames "when to stop exploring and commit
to an answer" as sequential decision-making under explicit costs. Giving the agent a prior
over latent state "qualitatively changes agent behavior". This supports making review cost
explicit in the agent's context.

**ATRBench ("Ask Now, Use Later"), 2026** [S18] (abstract only): it fixes each user's
preferences as "hidden ground truth, so success demands asking, not recall". Agents score
"at least 62 points below an oracle" given the preference, and "acquisition" is the
bottleneck. This is the closest design to our client-held slots: gold is available only
through ask(), so asking must be measured, and it cannot be recovered from context.

## 5. Anytime / time-to-decision / stability metrics

**ChaLearn AutoDL ALC, Liu et al. 2021** [S19] (full text read)
- "Any-time learning" metric: ALC = 1/log(1+T/t0) * integral_0^T s(t)/(t+t0) dt, with
  transformed time t~(t) = log(1+t/t0)/log(1+T/t0). Example values T=1200 s, t0=60 s. "The time
  axis is log scaled ... to put more emphasis on the beginning of the curve."
- They report a trade-off: one team's curve "goes up quickly at the beginning but
  stabilizes at an inferior final performance". The paper studies the effect of t0 on
  rankings.
- Borrow: a per-slot ALC on the evidence clock, where s(d) = 1 if the committed value on
  day d is correct. Choose t0 on purpose, since it sets how much early correctness counts.

**Halawi et al. 2024, LM forecasting** [S20] (full text read)
- Each resolved question is replayed at several simulated "retrieval dates" (n = 5,
  geometrically spaced between open and close). "We first average the Brier scores across
  retrieval dates for each question, then average across questions." Result: .179 Brier vs
  crowd .149.
- Leakage warning: choosing retrieval dates relative to the resolve date "would leak
  information, since the retrieval date would now depend on the resolve date".
- Borrow: evaluate the agent at every day of the stream, not only at the end. Guard the
  analogue of their leakage: never expose decidable-at or the gold change days in anything
  the agent can see, including artifact counts or stream length per slot.

**ForecastBench, Karger et al. 2024** [S21] (abstract only): a dynamic benchmark of 1,000
questions about "future events that have no known answer at the time of submission", which
avoids leakage by construction. Our frozen corpus gives up that guarantee, so keep the
held-out customers truly unseen.

**FlipFlop, Laban et al. 2023** [S22] (abstract only): after "Are you sure?", models "flip
their answers on average 46% of the time", with an average accuracy drop of 17%. For us,
flip rate is a stability metric, and challenge-induced flips are a rollback cause distinct
from new evidence. The reviewer must not add pressure beyond accept/reject.

## Implications for our benchmark

- **Keep the scripted oracle and exact typed match.** tau2 measured 12 to 13% critical
  user-simulator errors in retail and airline [S6], and swapping the simulator LLM alone
  moved tau-Bench success by up to 9 points [S7]. LLM judges show low intra-rater
  reliability [S9]. A deterministic oracle removes all three noise sources. State this
  with the numbers in the demo.
- **Validate that gold is derivable.** MultiWOZ label fixes alone moved JGA by 10 to 18
  points [S2]. Build a checker that re-derives each gold value, its decidable-at day, and its
  allowed citations from the spec using the grounding rules. Fail corpus generation if
  any slot is non-derivable or ambiguous (tau-bench's "only one possible outcome" [S5]).
- **Report per-slot and joint metrics.** Give per-slot time-to-trusted-decision (TTD),
  lag = TTD minus decidable-at, and a joint "record fully trusted" day. SGD's Avg GA vs
  Joint GA gap (0.560 vs 0.254) shows why one number hides slot skew [S1].
- **Add an anytime score.** Use a per-slot ALC over days with a log or discounted clock
  ([S19]), and average over evaluation days as in Halawi [S20]. Keep TTD as the headline.
  ALC summarizes the whole trajectory and punishes late correctness and flapping in one
  number.
- **Split rollbacks by cause, and tag seeded conflicts by type** (freshness / same-tier
  conflict / lower-tier noise / misinformation, per [S11]). Premature = committed before
  decidable-at. Stale-trap = kept or adopted a superseded value after the update. Count
  challenge-induced flips separately [S22].
- **Decorrelate order from recency.** Models favor later-presented evidence [S10], and
  re-rankers favor older, richer documents (Obsolete Ratio 84 to 98% [S12]). Seed
  late-arriving artifacts with old effective dates, and verbose stale KB pages that
  outrank terse corrections under vector similarity. Report a decision-level obsolete ratio.
- **Treat unseen customers as SGD's unseen services.** Hold out whole customers, including
  new slot-value vocabularies, since SGD's unseen-service drop came mainly from OOV values
  [S1]. Keep the 12-slot schema fixed, but vary values, sources, and conflict patterns.
- **Price asking explicitly and report a Pareto view.** Plot TTD or rollbacks against reviewer
  units, as ClarifyBench reports coverage against question count [S16]. Client-held slots
  must be answerable only through ask(), as in ATRBench [S18], so that asking is measured.
  Also measure over-asking on slots that are decidable from artifacts.
- **Run seeds for pass^k.** The oracle is deterministic but the agent is not. Report
  pass^k-style consistency ("slot trusted by day D in all k runs") [S5].
- **Prevent leakage.** Do not let artifact counts, stream length, or file names reveal
  decidable-at or change days [S20].
- **Silent errors equal a wrong commit with no escalation.** Report them separately, as FreshQA
  splits correctness from hallucination [S14]. AbstentionBench suggests stronger models
  will not fix this on their own [S15].

## Sources

- [S1] Rastogi et al., Towards Scalable Multi-domain Conversational Agents: The Schema-Guided Dialogue Dataset. https://arxiv.org/abs/1909.05855 (full text: https://ar5iv.labs.arxiv.org/html/1909.05855)
- [S2] Ye, Manotumruksa, Yilmaz, MultiWOZ 2.4. https://arxiv.org/abs/2104.00773 ; table: https://github.com/smartyfh/MultiWOZ2.4/blob/main/README.md
- [S3] Kim et al., Mismatch between Multi-turn Dialogue and its Evaluation Metric in DST. https://arxiv.org/abs/2203.03123
- [S4] Schatzmann et al., Agenda-Based User Simulation for Bootstrapping a POMDP Dialogue System. https://aclanthology.org/N07-2038.pdf
- [S5] Yao et al., tau-bench. https://arxiv.org/abs/2406.12045 (full text: https://arxiv.org/html/2406.12045)
- [S6] Barres et al., tau2-Bench: Evaluating Conversational Agents in a Dual-Control Environment. https://arxiv.org/abs/2506.07982
- [S7] Lost in Simulation: LLM-Simulated Users are Unreliable Proxies for Human Users in Agentic Evaluations. https://arxiv.org/abs/2601.17087
- [S8] Dou et al., SimulatorArena. https://arxiv.org/abs/2510.05444
- [S9] Rating Roulette: Self-Inconsistency in LLM-As-A-Judge Frameworks. https://arxiv.org/abs/2510.27106
- [S10] Su et al., ConflictBank. https://arxiv.org/abs/2408.12076 (full text: https://arxiv.org/html/2408.12076)
- [S11] DRAGged into Conflicts (CONFLICTS benchmark). https://arxiv.org/abs/2506.08500
- [S12] An et al., FRESCO. https://arxiv.org/abs/2604.14227
- [S13] HoH: Impact of Outdated Information on RAG. https://arxiv.org/abs/2503.04800
- [S14] Vu et al., FreshLLMs / FreshQA. https://arxiv.org/abs/2310.03214
- [S15] AbstentionBench. https://arxiv.org/abs/2506.09038
- [S16] Structured Uncertainty guided Clarification for LLM Agents (SAGE-Agent, ClarifyBench). https://arxiv.org/abs/2511.08798
- [S17] Calibrate-Then-Act: Cost-Aware Exploration in LLM Agents. https://arxiv.org/abs/2602.16699
- [S18] Ask Now, Use Later: Benchmarking the Proactivity Gap in Long-Lived LLM Agents (ATRBench). https://arxiv.org/abs/2605.28108
- [S19] Liu et al., Winning solutions and post-challenge analyses of the ChaLearn AutoDL challenge 2019. https://arxiv.org/abs/2201.03801 (full text: https://ar5iv.labs.arxiv.org/html/2201.03801)
- [S20] Halawi et al., Approaching Human-Level Forecasting with Language Models. https://arxiv.org/abs/2402.18563 (full text: https://arxiv.org/html/2402.18563v1)
- [S21] Karger et al., ForecastBench. https://arxiv.org/abs/2409.19839
- [S22] Laban et al., Are You Sure? ... The FlipFlop Experiment. https://arxiv.org/abs/2311.08596
