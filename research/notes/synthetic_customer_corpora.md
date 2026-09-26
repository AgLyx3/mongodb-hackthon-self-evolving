# Synthetic customer corpora: prior art for spec-to-artifacts benchmark generation

Researched 2026-09-26. Scope: how to render a typed gold spec (~6 fictional customers x ~12 decision slots) into a dated, multi-genre artifact corpus with planted supersessions, conflicts, distractors, and client-only facts, and how to audit it. Provenance tags: **[full text]** = read the paper/HTML text or repo source myself; **[HTML via summarizer]** = the HTML went through a fetch-and-summarize tool, and I did not grep every number against the raw text; **[abstract only]**.

## 1. hyper-tau-bench / τ^τ-bench (arXiv 2609.04611) [full text + repo source]

The closest analogue to our design. It turns policy "atomic facts" into a business's record corpus, and a developer agent must recover them.

**Method (Sec. 3, "Transformations"):** "(1) We decompose each policy into atomic facts: single statements that can be checked independently, such as a fee amount or the scope of a cancellation rule, and verify by hand that the facts wholly represent the original policy. (2) We group facts and prompt models to generate the artifacts a business would actually hold ... (3) We validate the outputs: every fact must stay recoverable from the corpus, stated in each carrier's own voice, and we audit artifacts for information they introduce beyond their assigned facts, removing any amount, date, or policy claim that neither a fact nor the domain database backs."
- Generators: "Claude Fable 5, GPT-5.6-sol, Claude Opus 5, and Claude Sonnet 5". Artifacts are "reviewed by three human auditors per transformation".
- Scale (Table 5): 3,328 atomic facts, 2,868 evidence artifacts, 144 client-held facts, 18 transformation types, 5 families (documents, conversations, operational exports, visuals, recordings). Text artifacts total "over 5.5 million tokens".
- Leakage and contamination: public domains were rebranded, and "every policy value" was replaced and re-derived so that "the database, the evidence artifacts, and the evaluation suite stay mutually consistent".

**Fact-carrier ratio (App. E):** one banking section has "145 facts across 86 developer-visible artifacts in eight genres; 26 artifacts carry facts and the rest carry none". About 39% of facts are owned by conversational records. "A manifest maps every artifact to the facts it must carry, which is what makes the corpus machine-checkable." In the transformation_pack.json I pulled for that section's client overlay, 62 of 85 artifact entries are `context_only`.

**Repo data model** (github.com/sierra-research/hyper-tau-bench, `data/tau2/hyper/sops/...`):
- `schema.json`: fact list `{id: "F009", statement: ...}` per section.
- `transformation_pack.json`: `transformations[]`, each with a `representation` (email_thread_archive, slack_mcp_dump, recorded_working_session, support_transcripts, website_screenshot, process_presentation, client_knowledge, ...) and `artifacts[]`. Per-artifact keys:
  - `included_fact_ids`: facts the artifact must land.
  - `depends_on_fact_ids`: facts it presupposes but does not state.
  - `context_only: true`: a distractor that carries no facts.
  - `pointer_for`: names a dead alternative, e.g. "Evergreen 1.5% uncapped workshop sketch (dead alternative, 2025-07-08 pricing workshop)".
  - `kit_filename`: neutral, agent-facing name.
  - Transcript bounds: `minimum/maximum_duration_minutes`, `minimum_speakers`, `min/max_words_per_minute` (e.g. 90–145 wpm, 3+ speakers).
- Top-level `transformation_bundles[]` group members into a task variant, and each carries a prose description of what the client holds.
- `client_knowledge` member: `fact_ids` (held only by the client), `confirmable_fact_ids` (the client adjudicates these but does not own them), and `discovery_tiers` per held fact. The tiers are `pointer` (an artifact refers the question to the client), `caveat` (the only trail is boilerplate such as "has not been refreshed since"), and `silent` (src/tau2/hyper/transformations/client_knowledge.py).
- `eval_manifest.json` (email archives): `threads[]` with `authoritative_fact_ids`, `historical_fact_ids`, `decision_date`, and `scope_change_histories`. Per fact, that is a list of events `{thread, status: superseded|final_current, decision_date}`.
- Screenshot `eval_manifest.json` keeps versions (`v1_ambiguous`, `v2_clarified`) under a policy: "Never overwrite an ambiguous artifact when clarifying it."

**Automated validators we can copy** (src/tau2/hyper/transformations/email_threads.py, base.py, compile.py):
- Unknown fact IDs are rejected. Every `.eml` must parse and carry From, To, Date, Subject, Message-ID, MIME-Version, Thread-Topic, and Thread-Index. Duplicate Message-ID or Thread-Index values are rejected, and each thread needs at least 4 messages.
- The manifest's `{filename: authoritative_fact_ids}` "must exactly match artifact filenames and included_fact_ids". `thread_count` must be correct.
- Scope histories: a fact "cannot be both current and historical". Each history needs at least 2 events, must end in exactly one `final_current` after `superseded` events, and "events must be chronological". Each event's date must match its thread's `decision_date`.
- Compile-time coverage report: facts not covered by any active transformation are listed (`uncovered_fact_policy`: fallback|error).
- Client-overlay contract (`_check_client_overlay`): a client variant is the base bundle minus the held facts. Members may be substituted but never added. Each replacement's authority = the base authority minus the client-held facts. Everything else "must match the base verbatim".
- The paper (App. D) adds: "each fact's presence in its assigned carrier is machine-checked, thread counts and chronology are validated, and the checks re-run whenever an artifact changes."
- `to_text()` renders an artifact to plain text "for NL fact-coverage judging". `kit_text()` must be free of author-side annotations "the Developer must never see (fixture labels, timeline notes)".

**Authoring-prompt rules (App. D, email guide), with pitfalls named:**
- Landing facts: "State the fact as an operational sentence in the author's voice, not the schema's." Best pattern: someone asks an operational question, and the decision is the answer.
- Supersession: "Banned constructions: 'this supersedes earlier guidance,' 'the complete list is,' any guardrail addressed to the reader. A later thread simply decides something different, with a concrete business trigger."
- Distractors "may brush policy vocabulary but never decide anything. Do not quarantine information: if only one thread ever contains policy-shaped language, the signal is findable by elimination."
- Class anonymity: "The largest artifact in each family must carry no facts; the size rank of carriers must vary across families; any marker that appears on a carrier must also appear on artifacts that carry nothing."
- Value grounding: "Every amount, date, and direction word ... must derive from the domain database, never invented."
- Mechanical realism: opaque message IDs minted at the sender's domain. Business-hour timestamps with "same-day reply clusters and multi-day gaps, never a fixed step." Message length is a distribution ("+1" one-liners, most 20–70 words). "noise everywhere is its own fingerprint."
- Visuals: "no oversized REJECTED or SUPERSEDED stamps"; a "final disposition lives in a governance artifact elsewhere", such as a dated email or decision log. Also "Avoid putting all authoritative nodes in one color, one column, or the only polished frame."

**Client simulator knowledge boundary (Sec. 3, App. I):** "The client's system prompt is rendered deterministically from the fact schema and embeds only the facts it may discuss, so nothing else can leak." The prompt has three sections:
- `<what_only_you_know>`: the client answers these plainly.
- `<records_in_conflict>`: "the documents cannot settle which is current -- only you can". The client states the current version and does not volunteer other conflicts.
- `<questions_you_can_settle>`: yes/no confirmation only. "Never volunteer a version they did not offer."

Everything else goes back to the records ("Outside your listed points your memory is unreliable"). Because the boundary is a set of fact IDs, "elicitation is measurable".

Limitation they state (Sec. 6): "every policy fact is planted in at least one artifact or held by the client, the corpora are audited for mutual consistency"; "noticing that the specification has holes is part of the job we do not measure."

## 2. Era by Eon Benchmark (arXiv 2609.09853) [full text, key quotes grepped from HTML]

- A company is defined by "Industry, company size, business model, application portfolio, and a seed". "One seeded entity graph supplies shared company data to simulators of Salesforce, Zendesk, Slack, Gong, and other products."
- Each simulator "rebuilds the tenant's entity graph from the same seed and configuration and projects it". IDs are derived deterministically in each vendor's real format.
- Internal DBs: an LLM designs the schema, then a validator "rejects a design that creates a second identity for a shared entity" and "rejects a proposed unanswerable question when the schema contains the required information."
- Answers are computed from the final records ("cannot disagree with the data"). A reachability audit "re-reads every audited fact through each simulator's native API and through its MCP tools, and asserts that the value read back equals the stored answer", and it "identified real defects".
- Lazy solvers: "one drops a condition, one ignores the join ..., one aggregates over all rows ... Any question that a lazy solver answers exactly correctly is measuring nothing."
- Realism scorecard: marginal, joint, temporal, structural, and content axes. A boosted-tree classifier tries to tell real rows from "an independently shuffled copy" to catch missing correlations. The adversarial detector's tells are "Dunn, Dunn2, Dunn3" names, flat histograms, timestamps that "advance in identical steps", and "Every parent record has exactly the same number of children."
- Results: across 23 companies, mean realism went from 61.8 to 97.0, and the share of records flagged as synthetic went from 55.2% to zero. They also guard against overfitting the generator: every change is scored "on a fixed seed that was never used during development".
- Time: "day 0 is the empty system, day 1 the full history, and day 2 adds one further day of change, with the answer key recomputed at each state." This maps onto our "decidable-at day" idea.

## 3. AgentMercury (arXiv 2608.20634) [HTML, partial grep]

- A world is factored as company identity, service graph, state schema, initial state s0, and world-level invariants R. Invariants are "properties that the world requires to hold but does not itself enforce", each with "an executable verification condition". Grading is deterministic and post-episode, with visible and hidden invariant views.
- Scale: 4,783 environments, 14 industries, 50 countries (abstract). Generated worlds must pass "12 structural validators".
- Failure mode: "collapse of a cross-service constraint, where the trigger and target of an invariant are incorrectly placed within the same service". This hit 10 of 30 briefs for GPT-5.4, and it "cannot be detected reliably from the generated specification alone".
- Lesson for us: validate cross-system facts (DB vs ticketing vs CRM) by execution, not by reading the spec.

## 4. EnterpriseRAG-Bench (arXiv 2605.05253, Onyx) [HTML, key quotes grepped]

- About 500K docs across 9 sources (Slack, Gmail, Linear, Drive, HubSpot, Fireflies, GitHub, Jira, Confluence) and 500 questions.
- Coherence comes from human-vetted scaffolding: company overview, initiatives, employee directory, source structure, and per-location "agents.md" format specs.
- Noise: 8% of documents are shuffled into the wrong location. Near-duplicates are a "New version generated with specific facts changed; may cross source types", and the pairs are tracked to build "conflicting info" questions. Constrained questions add **anti-hallucination facts**: "negative statements that catch errors a system might make if it retrieves a distractor document".
- Pitfalls they measured:
  - Uncontrolled generation gave ">40%" near-duplicates in a 100-doc test.
  - "Unix timestamps converge on round numbers like 123456789, company names default to 'ACME' variants ... could provide unintended retrieval signals."
  - A question "back-generated from one document may be equally well or better answered by unrelated document elsewhere". High-volume documents may "supplement or supersede a project-based gold answer".
  - In-cluster similarity is 0.61 synthetic vs 0.56 for real Onyx data.
- Their fix: pool BM25, vector, and agent retrieval, then a three-judge consensus relabels gold docs, and uncorrectable questions are discarded.

## 5. WinSyn (arXiv 2609.12171, Microsoft Research India) [HTML, key quotes grepped]

- Pipeline: company and employees → epics DAG → tasks → daily diaries → QA → emails → sentence attribution → distractors. The diaries are a hidden source of truth.
- "Gold answers are frozen before any email communication is generated. Emails only add details that do not change the gold answers."
- Distractor types: process noise (OOO replies, HR notices), **correction chains** ("an initial misstatement that is subsequently corrected, with the final state matching ground truth"), and tangential projects with overlapping vocabulary ("Dashboard 2.0" vs "Reporting Dashboard"). "Each distractor is validated to ensure no gold answer would change in its presence." Process noise is auto-approved, and the other types go through LLM comparison.
- Sentence-level attribution goes answer → diary → communication, with sentences indexed by (epic_id, task_id, date, section, parent_artifact_id).
- Scale: 4 datasets of 127–181 emails, 22–25 employees, 100–117 days, and 22–28 questions. They admit they have not "quantified distributional similarity to actual enterprise data".

## 6. HERB (arXiv 2506.23139, Salesforce; EMNLP 2025 Industry) [HTML via summarizer]

- Query-first design: manually defined queries, then workflows synthesize the evidence, and artifacts are "explicitly linked to the queries they support".
- Scale: 530 employees, 30 products, 39,190 artifacts (33,632 Slack messages, 321 transcripts, 400 docs, 3,562 PRs, 575 URLs); 815 answerable and 699 unanswerable queries. Unanswerable queries pair templates with workflows that lack the evidence.
- Eight distractor types include product renames mid-lifecycle, legacy feedback from older versions, multiple planning teams, and competitor docs.
- Limitations: heavy manual effort. Systems "should not be explicitly tuned to the specific workflows or distractor patterns used to generate the data".

## 7. CRMArena-Pro (arXiv 2505.18878) [HTML via summarizer]

- LLM (gpt-4o) generated Salesforce orgs: 25 objects, 21 latent variables, 29,101 B2B and 54,569 B2C records.
- Validation: de-duplication, format checks against the schema, then rule and LLM content checks for "logical consistency and plausibility".
- Expert realism study: 66.7% (B2B) and 62.3% (B2C) rated realistic or highly realistic. That is weaker evidence than Era's statistical detector.

## 8. EnterpriseOps-Gym (arXiv 2603.13594, ServiceNow) [abstract only]

164 DB tables, 512 tools, and 1,150 **expert-curated** tasks over 8 verticals. The best model (Claude Opus 4.5) reaches 37.4%. Refusal of infeasible tasks tops out at 53.9%. This is a contrast case: hand-curated tasks, not a generated corpus.

## 9. Pitfall references outside enterprise

- Gururangan et al. 2018, "Annotation Artifacts in NLI Data" (arXiv 1803.02324) [abstract only]: a model reading the hypothesis alone gets the label right on "about 67% of SNLI" and "53% of MultiNLI". This is the canonical **artifact-only baseline** idea. For us: can a classifier that never sees the question pick the gold-carrying artifact from surface features alone?
- Kucia & Gawlik 2026, "Beyond Benchmark Scores" (arXiv 2609.14579) [abstract only]: synthetic queries average 15.7 words vs 6.8 for authentic ones. Optimizing on synthetic queries "selected a higher-latency hybrid retriever" costing up to 8x latency. Synthetic evaluation sets drift from real usage.

## Pitfall catalogue (with who documents it)

| Pitfall | Source | Automatable check |
| --- | --- | --- |
| Gold value leaks into distractors, or a distractor accidentally decides a slot | τ^τ (distractors "never decide anything"); WinSyn (the gold answer must not change); EnterpriseRAG ("equally well answered by unrelated document") | Grep every non-carrier for every gold and stale value string of that slot; an LLM judge asks "does this artifact decide slot X?" |
| Artifact introduces extra facts (numbers, dates, rules) | τ^τ step 3 (remove claims "neither a fact nor the domain database backs") | Extract all numbers, dates, and emails; each must map to the spec or the DB |
| Supersession is signposted ("this supersedes") or shown with stamps | τ^τ App. D banned constructions and "Lifecycle tells" | Regex blocklist: supersede, deprecated, "no longer", FINAL, OBSOLETE, "latest version" |
| Only the carrier looks special (size, format, polish, marker) | τ^τ class anonymity; Gururangan | Size-rank check per genre; train a surface-feature classifier to separate carriers from non-carriers and require near-chance accuracy |
| Signal findable by elimination (only one policy-shaped doc) | τ^τ | Require distractors in the same genre that use slot vocabulary |
| Synthetic tells: round or step timestamps, ACME names, name2/name3, flat histograms | Era; EnterpriseRAG | Check inter-message gap variance, business hours, a name blocklist, and duplicate-name suffixes |
| Near-duplicate homogeneity | EnterpriseRAG (>40%) | Embedding cosine between artifacts; cap max similarity |
| Fact not actually reachable through the delivered channel (e.g., the DB) | Era reachability audit | Re-read each DB-carried slot through the agent's own tool |
| Client simulator leaks facts it should not hold | τ^τ (rendered deterministically from fact IDs) | Unit test: the rendered client prompt contains exactly the held and conflict slot values, and no others |
| Generator overfit to the audited seed | Era (score on a fixed unseen seed) | Hold out one customer from generator tuning |
| Trivial questions (solvable while ignoring a condition) | Era lazy solvers | "Latest-only" or "first-mention" baseline solver must fail on supersession slots |

## Generation recipe for our suite

1. **Typed spec (pydantic), hand-written, no LLM.** A list of customers, each with `stack` and `slots` (12 slots). Each slot holds:
   - `value_history: [{value, decided_on, carrier_id, status: superseded|final_current}]` (τ^τ scope_change_histories);
   - `holder: corpus|client_only|client_confirmable` plus `discovery_tier: pointer|caveat|silent`;
   - `trap: supersession|same_tier_conflict|none`.

   Derive `decidable_at` = the date of the final_current event, or the date of the client conversation for client-only slots (Era day-states). Give each customer a seed. Hold one customer out of generator tuning (Era).
2. **Artifact plan (deterministic, from the spec).** Emit a manifest like transformation_pack.json. Every artifact gets `id, genre, date, author, kit_filename, included_slot_ids, historical_slot_ids, depends_on, context_only, pointer_for`.
   - Carriers should be about 30% of artifacts; τ^τ uses 26/86 (App. E) and 62/85 context_only (the pack I pulled).
   - Each slot gets at least one current carrier. Supersession slots get at least one historical carrier dated earlier. Same-tier conflicts get two carriers of equal authority and move the resolution to the client (`records_in_conflict`).
   - Randomize carrier size rank and genre per customer, so the largest artifact in each genre is context_only.
3. **Structured artifacts rendered by code, not LLM.** This covers the live MongoDB DB, OpenAPI docs (auth method, rate limit), Jira export JSON, `.eml` headers, and `.vtt` timing. Values come only from the spec (τ^τ "value grounding"). Timestamps use business hours with jittered gaps and reply clusters.
4. **LLM writes prose bodies only, one artifact per call.** Pass only that artifact's assigned slot statements, persona voices, date, and thread context. Include the τ^τ rules in the prompt:
   - operational voice;
   - no supersession narration;
   - distractors may use slot vocabulary but decide nothing;
   - length distribution and light typos.

   Freeze the output with content hashes.
5. **Client simulator prompt rendered from the spec** (τ^τ App. I template). Sections are `what_only_you_know`, `records_in_conflict`, and `questions_you_can_settle`. Everything else is "check the records".
6. **Automated audit (CI; fail the build on any violation):**
   - a. Schema: `.eml` headers present and parseable, unique Message-ID and Thread-Index, `.vtt` parseable with ≥3 speakers and 90–145 wpm, Slack and Jira JSON validate against their schemas.
   - b. Manifest ↔ spec: every slot is covered. Supersession histories are chronological and end in exactly one final_current. No slot is both current and historical in one artifact. Client-only slot values appear in no artifact (exact-string and normalized-number grep).
   - c. Recoverability: an LLM extractor reads each carrier alone and must return the assigned value (τ^τ "every fact must stay recoverable").
   - d. No extra facts: regex-extract every number, money amount, date, duration, email, and URL. Each must appear in the spec, the persona table, or the DB. Otherwise flag it (τ^τ step 3).
   - e. Leakage: the current gold value must not appear in any context_only artifact or in any artifact dated before `decidable_at`. An LLM judge, per (artifact, slot), must answer "decides nothing" for non-carriers (WinSyn distractor validation).
   - f. Signposting blocklist regex over prose (supersede, deprecated, obsolete, "no longer valid", "FINAL", "correct value is").
   - g. Class anonymity: carriers' size rank is not extreme within each genre. A logistic regression on surface features (length, word count, has-table, header count, polish/typo rate) predicting carrier vs non-carrier should score AUC ≈ 0.5 (Gururangan artifact baseline).
   - h. Synthetic tells: no fixed-step timestamps, no ACME or name2 patterns, max pairwise embedding cosine below a threshold (EnterpriseRAG, Era).
   - i. Reachability: DB-carried slots are re-read through the agent's MongoDB tool and must equal gold (Era).
   - j. Baseline solvers must fail on trap slots:
     - "first mention" and "most frequent value" solvers must fail supersession slots;
     - a "latest-dated doc of any tier" solver must fail tier-conflict slots;
     - a "corpus only" solver must fail client-only slots (Era lazy solvers).
7. **Human audit (hackathon-sized).** One person reads each carrier against its manifest line and spot-checks 20% of distractors. Record sign-off in the manifest. On a fix, add a new version and never overwrite (τ^τ versioning policy).
8. **Freeze.** Store the spec hash, manifest, corpus hashes, and audit report. Agent scores are reported against that frozen version (EnterpriseRAG: "no retroactive rescoring").

## Sources

- τ^τ-bench paper: https://arxiv.org/abs/2609.04611 (PDF text read in full; Sec. 3, App. B, D, E, I)
- τ^τ-bench repo: https://github.com/sierra-research/hyper-tau-bench
  - https://github.com/sierra-research/hyper-tau-bench/blob/main/data/tau2/hyper/sops/banking_knowledge/sections/checking_atm_fee_rebates_and_credits/client_overlay_001/transformation_pack.json
  - https://github.com/sierra-research/hyper-tau-bench/blob/main/data/tau2/hyper/sops/airline_plus/sections/cancelling_reservation/website_screenshot_001/eval_manifest.json
  - https://github.com/sierra-research/hyper-tau-bench/blob/main/src/tau2/hyper/transformations/email_threads.py
  - https://github.com/sierra-research/hyper-tau-bench/blob/main/src/tau2/hyper/transformations/client_knowledge.py
  - https://github.com/sierra-research/hyper-tau-bench/blob/main/src/tau2/hyper/transformations/base.py
  - https://github.com/sierra-research/hyper-tau-bench/blob/main/src/tau2/hyper/transformations/compile.py
- Era by Eon: https://arxiv.org/abs/2609.09853 , https://arxiv.org/html/2609.09853v1
- AgentMercury: https://arxiv.org/abs/2608.20634 , https://arxiv.org/html/2608.20634
- EnterpriseRAG-Bench: https://arxiv.org/html/2605.05253v2 , https://github.com/onyx-dot-app/EnterpriseRAG-Bench
- WinSyn: https://arxiv.org/html/2609.12171
- HERB: https://arxiv.org/html/2506.23139 , https://github.com/SalesforceAIResearch/HERB
- CRMArena-Pro: https://arxiv.org/html/2505.18878v1
- EnterpriseOps-Gym: https://arxiv.org/abs/2603.13594
- Annotation Artifacts in NLI Data: https://arxiv.org/abs/1803.02324
- Beyond Benchmark Scores: https://arxiv.org/abs/2609.14579v1
