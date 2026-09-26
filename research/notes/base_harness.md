# Base harness research (2026-09-26)

Goal: avoid building the base agent harness from scratch for the self-evolving FDE harness
(AML / transaction-monitoring alert triage -> {close_false_positive, request_info, escalate}).
Stack constraints: Python 3.12, LangGraph (+ MongoDB checkpointer/store), Atlas, OpenRouter, FastAPI, Next.js, $10 LLM budget.

Legend: [V] = verified from repo/API today; [U] = unverified / inferred.

---

## A. Domain-specific (AML / KYC / TM triage) open-source harnesses

### Search performed
- `gh search repos` for: "aml agent langgraph", "anti-money laundering llm", "aml investigation agent",
  "aml alert", "aml copilot", "kyc agent", "transaction monitoring agent", "financial crime agent",
  "sanctions screening agent", "finos ai", "sar generation llm", "compliance agent langgraph".
- Web search for AML-agent papers with released code.

### Finding: nothing "solid" exists [V]
Every AML-agent repo found is a **single-author portfolio / hackathon project**, 0-2 stars, created in 2026,
most **without a license** (unlicensed = legally not reusable). No FINOS project provides an AML triage agent
(FINOS hits were hackathon repos and the AI Governance Framework, which is controls, not an agent).
The mature open-source AML systems (Jube - AGPLv3, C#; Marble - decision engine; Tazama - TS/ISO20022)
are **rule/ML transaction-monitoring engines**, not LLM agent harnesses — useful only as vocabulary/inspiration.

| Repo | Stars | Last push | License | Lang/stack | Notes |
|---|---|---|---|---|---|
| ameshram/agentic-alert-triage | 0 | 2026-09-16 | MIT | Python, raw Anthropic SDK tool loop | **Best domain reference.** See below. |
| Kazolah/aml-investigation-agent | 0 | 2026-07-06 | MIT | LangGraph **0.2.76** (pinned, old), langchain-openai, SQLite checkpointer, Streamlit | Fixed 9-node pipeline (ingest→enrich→CDD→watchlist→LLM reasoning→router→human_review interrupt→SAR→audit). Only one LLM node; prompt in `agent/prompts/reasoning_prompt.py`. 5 alert fixtures. |
| erpkb-stack/aml-investigation-agent | 0 | 2026-09-23 | MIT | FastAPI + Alembic/SQL + RAG + MCP client, multi-LLM (openai/gemini/ollama/deterministic) | Large app, not a harness; too much surface to adopt. |
| Zahoor-ishfaq/aml-investigation-agent | 0 | 2026-07-08 | none | Python, rules + ReAct loop | No license -> can't reuse. |
| FerdinandZhong/anti-money-laundering | 0 | 2026-09-21 | none | Python, MCP server w/ 5 tools | No license. |
| basavarajshepur-lab/aml-copilot | 0 | 2026-07-13 | none | Python multi-agent triage + HITL | No license. |
| neo4j-product-examples/graphrag-kyc-agent | 30 | 2025-07-23 | none in API | OpenAI Agents SDK + Neo4j MCP | Official-ish Neo4j example; KYC not TM triage; Neo4j-bound; stale. |
| JkayAy/kyc-aml-alert-triage | 0 | 2026-09-20 | none | TypeScript | Wrong language, no license. |
| ejimeoghenefejiro/AML-Agent-Bench | 1 | 2026-08-30 | MIT | C# | Benchmark, not a harness. |
| RiskTagger (Connector-Tool/RiskTagger, arXiv 2510.17848) | [U] | [U] | [U] | Web3 crypto ML annotation | Different task (on-chain annotation). |

### ameshram/agentic-alert-triage — closest match, worth *mining*, not adopting [V]
- https://github.com/ameshram/agentic-alert-triage — MIT, created 2026-09-14, ~47 KB, 0 stars.
- Layout: `src/agentic_triage/{agent.py, llm.py, tools.py, prompts.py, policy.py, retrieval.py, security.py, schemas.py, pipeline.py, service.py}`,
  `eval/{run_eval.py, judge.py, thresholds.yaml}`, `scripts/generate_synthetic_data.py`, tests.
- Design: LLM runs a manual tool-use loop (tools: `get_transaction_history`, `get_entity_profile`,
  `check_watchlist`, `search_prior_cases` (RAG) + terminal `submit_assessment`) under step/cost/latency budget;
  outputs `RiskAssessment` (level, confidence, narrative); a **pure deterministic `policy.py`** maps to
  `auto_close / hold / escalate` with guardrail overrides (injection, budget, watchlist hit).
- Eval: FNR (auto-closed-but-suspicious) gated <= 0.05, escalation recall, adversarial block rate = 1.0,
  LLM-judge narrative score, cost/latency; CI gate exits non-zero. `MockLLM` lets everything run offline.
- Fit: its action set maps almost 1:1 to ours (auto_close≈close_false_positive, hold≈request_info, escalate).
  `policy.py` is exactly a "control hook"; `prompts.py` = context; `tools.py` = tools; `retrieval.py` = retrieval policy;
  `eval/thresholds.yaml` = gates. 
- Red flags: 12 days old, single author, 0 stars; **Anthropic-only client** (`AnthropicClient`, tool specs in
  Anthropic format) — would need an OpenAI-compatible client for OpenRouter; not LangGraph; components are Python
  modules, not declarative files (prompt is a Python string).
- Verdict: **copy ideas + possibly the synthetic data generator/tool signatures/policy/eval metrics (MIT, attribute it)**;
  don't adopt as the runtime.

### Conclusion for A
No production-grade or community-maintained open-source AML triage agent harness exists. Use a general
harness (Section B) and seed its domain content from `ameshram/agentic-alert-triage` (MIT) patterns.

---

## B. General-purpose base harnesses

### B1. LangChain Deep Agents (`deepagents`) — TOP PICK [V]
- Repo: https://github.com/langchain-ai/deepagents — MIT, ~29.8k stars, pushed 2026-09-26 (daily); PyPI `deepagents==0.7.19` (2026-09-24), Python >=3.11.
- What it is: "the batteries-included agent harness" built on LangChain `create_agent` -> LangGraph `CompiledStateGraph`
  (so `checkpointer=` and `store=` accept `MongoDBSaver` / `MongoDBStore` directly).
- `create_deep_agent(model, tools, *, system_prompt, middleware, subagents, skills, memory, permissions, backend,
  interrupt_on, response_format, state_schema, context_schema, checkpointer, store, ...)` (verified in `libs/deepagents/deepagents/graph.py`).
- Harness components and where they live (all verified in source):
  - **Instructions/context**: `system_prompt` + `memory=["/memory/AGENTS.md"]` (MemoryMiddleware loads AGENTS.md files into system prompt).
  - **Skills**: `skills=["/skills/base/", "/skills/customer_x/"]` -> directories with `SKILL.md` (YAML frontmatter name/description + markdown),
    Anthropic Agent-Skills spec, progressive disclosure; **later sources override earlier (layering base -> customer)** — perfect for per-customer mutations.
  - **Tools**: plain Python callables/`BaseTool`/MCP; built-ins (ls/read_file/write_file/edit_file/glob/grep/execute/task) can be hidden via
    `HarnessProfile(excluded_tools=...)`.
  - **Control hooks**: LangChain `AgentMiddleware` (before/after model, wrap tool call) + `interrupt_on` (HITL approve/edit/reject) + `permissions`
    (filesystem allow/deny rules) + `response_format` (structured output -> enforce disposition enum).
  - **Subagents**: declarative `SubAgent` dicts (name, description, system_prompt, tools, skills...).
  - **Backends** (where files live): `StateBackend` (default, in-graph), `FilesystemBackend(root_dir=...)` (real disk -> git-diffable),
    `StoreBackend(namespace=..., store=BaseStore)` (**MongoDBStore works here -> harness versions as Mongo namespaces**), `CompositeBackend`.
- OpenRouter: first-class — built-in `profiles/provider/_openrouter.py` requires `langchain-openrouter>=0.2.0` (PyPI 0.2.9, 2026-09-22);
  use `model="openrouter:<vendor/model>"` or pass a `ChatOpenAI(base_url="https://openrouter.ai/api/v1")` instance [model-string form: U, instance form: standard].
- MongoDB fit: official `langchain-ai/langchain-mongodb` monorepo (MIT, pushed 2026-09-25) ships `langgraph-checkpoint-mongodb 0.5.0`,
  `langgraph-store-mongodb 0.4.0`, and `langchain-mongodb-deepagents-vfs` (Atlas-backed DeepAgents backend — **but it forwards reads/writes to S3**,
  so skip it; use `StoreBackend` + `MongoDBStore` or `FilesystemBackend` instead). MongoDB DevRel published a DeepAgents adapter (archived
  mongodb-developer/MongoDB-LangChain-DeepAgents-VFS-Adapter -> moved into langchain-mongodb) = good "sponsor alignment" story.
- Adaptation effort for triage: ~2-3 h. Write 4-6 tools (get_alert, get_transactions, get_kyc_profile, check_watchlist, search_prior_cases),
  `response_format=Disposition` pydantic model, AGENTS.md per customer, 2-4 SKILL.md files (e.g. structuring, gambling-chip-walking,
  fintech-p2p-mule), a deterministic policy middleware. Mutations = file diffs under `harness/<customer>/<version>/{AGENTS.md, skills/, tools.yaml, hooks.yaml, retrieval.yaml}`.
- Red flags: (1) very fast release cadence (several releases/day) -> **pin `deepagents==0.7.19`**; (2) internals are large (~20 middleware
  modules) — don't read them, only use the public factory; (3) default tool suite + profile prompt adds tokens per call; hide unused tools
  and disable the general-purpose subagent to save budget; (4) "trust the LLM" security model — the agent can write to files the backend exposes,
  so point the triage agent's backend at a read-only view (use `permissions`) so it can't edit its own harness; (5) deprecation: `model=None` default.

### B2. LangChain v1 `create_agent` + middleware — RUNNER-UP [V]
- `langchain==1.4.2` (2026-09-18), MIT. `libs/langchain_v1/langchain/agents/factory.py` + middleware:
  `human_in_the_loop, model_call_limit, tool_call_limit, model_retry, model_fallback, pii, summarization, tool_selection, context_editing, todo, ...`.
- Same LangGraph graph, same checkpointer/store params, same middleware hook API that deepagents builds on — but no skills/AGENTS.md/filesystem.
- You'd write a ~50-100 line loader: read `harness/<ver>/system.md`, concatenate selected `skills/*.md`, map `tools.yaml` to a fixed Python tool
  registry, and wrap `hooks.yaml` into middleware. Fewer tokens, fully understandable in <1 h, zero surprise behavior.
- Choose this if deepagents' extra tools/prompt/abstractions get in the way during the first hour. Migration between the two is cheap
  (deepagents = create_agent + middleware).
- `langchain-ai/react-agent` (MIT, 850 stars, pushed 2026-09-25) is the older LangGraph Studio template (`graph.py/prompts.py/tools.py/context.py`
  + `langgraph.json`) — clean but prompts are Python strings; superseded by `create_agent`.

### B3. Others checked (not recommended as base)
| Candidate | Facts [V] | Why not |
|---|---|---|
| mini-swe-agent (SWE-agent/mini-swe-agent) | MIT, ~8k stars, pushed 2026-09-21; YAML configs (`config/default.yaml`, `mini.yaml`), `agents/default.py`; has `openrouter_model.py` | Bash-only action space, not LangGraph; great minimalism reference but wrong tool paradigm. |
| smolagents (huggingface) | Apache-2.0, ~29.5k stars; prompts in YAML (`prompts/toolcalling_agent.yaml`) | Code-agent paradigm, not LangGraph, no Mongo checkpointer. |
| OpenAI Agents SDK (openai/openai-agents-python) | MIT, ~29.7k stars; LiteLLM & any-llm model extensions | Not LangGraph; own tracing/sessions; would fight the fixed stack. |
| Claude Agent SDK (anthropics/claude-agent-sdk-python) | MIT, ~8.2k stars; OpenRouter documents `ANTHROPIC_BASE_URL=https://openrouter.ai/api` for it | Wraps Claude Code CLI subprocess; heavy per-call context (costly on $10); not LangGraph. Has skills/hooks natively though. |
| tau2-bench (sierra-research) | MIT, ~2.1k stars; domain = `data/tau2/domains/<d>/{policy.md, db.json, tasks.json}` + `src/tau2/domains/<d>/tools.py`; `agent/llm_agent.py` via litellm | Benchmark framework (user simulator, orchestrator), not a product harness. **Copy its domain layout** (policy.md + db + tools + tasks) for our per-customer data/eval. |
| mongodb-developer LangGraph labs (ai-agents-lab, multimodal-agents-lab, event-venue-operator, agent-memory-lab) | MIT/Apache, 7-77 stars | Tutorials/notebooks; useful for MongoDBSaver/MongoDBStore + vector-search snippets only. |
| mongodb-partners/mongodb-temporal-ai-agent-qs | Apache-2.0, pushed 2026-05-11; txn fraud approve/reject + human review, Temporal + Bedrock | Closest MongoDB-official domain demo, but Temporal/Bedrock, not LangGraph — mine for data model/UI ideas only. |

### B4. Harness-evolution paper repos (seed harnesses) [V unless noted]
| Paper | Code | License | Seed harness usable? |
|---|---|---|---|
| Meta-Harness (2603.28052) | https://github.com/stanford-iris-lab/meta-harness (~1.6k stars, pushed 2026-09-11) | MIT | **Yes, as a pattern**: `reference_examples/text_classification/` has seed harnesses `agents/no_memory.py`, `fewshot_all.py`, `fewshot_memory.py` implementing `MemorySystem.predict()/learn_from_batch()`; litellm with `openrouter/openai/gpt-oss-120b` default in `config.yaml`; proposer = Claude Code via `claude_wrapper.py`; `ONBOARDING.md` produces a `domain_spec.md`. Classification framing is close to our disposition task. Not LangGraph. README: "not tested beyond verifying that it runs". |
| Self-Harness (2606.09498) | https://github.com/qzzqzzb/Self-Harness (113 stars, pushed 2026-07-02) | **none** | Terminal-Bench/Harbor-specific; has proposer `hooks.py`, `acceptance/run_acceptance_gate.py` (held-in/held-out regression gate). Idea source only — no license. |
| VeRO (2602.22480) | https://github.com/scaleapi/vero (30 stars, pushed 2026-09-17) | MIT | Baselines under `harness-opt-bench/.../baseline/target/src/*/agent.py` ("this whole file is the optimizable surface"); Harbor-based. Useful for versioned-snapshot + budgeted-eval design, not as runtime. |
| HarnessCompass (2608.01918) | none found | - | No code located. |
| HarnessDev (2609.01437) | project page self-developing-agents.github.io (no readable code links); `harnessdev/harnessdev` GitHub repo exists but is **empty** | - | Not available. [U whether code is elsewhere] |
| Community: SuperagenticAI/metaharness | 173 stars, MIT/Apache dual (NOASSERTION in API), pushed 2026-09-02 | - | Library/CLI for Meta-Harness-style optimization with Codex proposer [features U]. |

---

## Ranked recommendation

1. **Top pick: `deepagents==0.7.19` (LangChain Deep Agents) on LangGraph, with `langchain-openrouter`, `MongoDBSaver` + `MongoDBStore`.**
   Why: it is the only candidate whose *native* extension points are exactly our mutation surfaces as files — AGENTS.md (context),
   SKILL.md dirs with layered override (skills), tool list, middleware + `interrupt_on` + `permissions` (control hooks), subagents —
   while being LangGraph-native (Mongo checkpointer/store drop in), MIT, heavily maintained, and OpenRouter-aware out of the box.
   Harness version = a directory (git-diffable) or a MongoDBStore namespace; the proposer emits diffs; the FDE approves; promotion = pointer swap.
   Mitigations: pin version, hide built-in fs/execute/task tools, `response_format` for the 3-way disposition, read-only backend for the triage agent.
2. **Runner-up: plain LangChain v1 `create_agent` + our own ~100-line file loader** (same middleware API, fewer tokens, zero magic).
   Fall back to this if deepagents costs more than ~1 h of fighting.

Borrow (not adopt): domain tools/policy/eval-metric design and synthetic generator from **ameshram/agentic-alert-triage** (MIT — keep attribution);
per-domain layout `policy.md / db.json / tasks.json / tools.py` from **tau2-bench**; proposer-loop + held-out acceptance-gate structure from
**Meta-Harness text_classification** (MIT) and Self-Harness (idea only, unlicensed).
