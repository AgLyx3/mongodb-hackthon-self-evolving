---
paths:
  - "services/**/memory/**"
  - "services/**/agent/**"
  - "services/**/adapters/mongo/**"
  - "services/**/models/**"
---

# Agent memory and self-evolution

This is the judged core of the project: a harness that remembers and adapts
over time, with MongoDB Atlas as the memory layer. Framing follows MongoDB's
"Agent Memory Inside the Harness" (mongodb.com/company/blog/technical/agent-memory-inside-harness).

## State is not memory

Conflating these is the most common mistake in this layer. Keep them in
separate collections with separate code paths.

| | State | Memory |
| --- | --- | --- |
| Lifetime | One run | Across sessions |
| Source | Produced by execution | Curated, learned, extracted |
| Used for | Resuming a run | Informing new runs |
| LangGraph piece | `langgraph-checkpoint-mongodb` (checkpointer) | `langgraph-store-mongodb` (`MongoDBStore`) |

## Memory kinds

- **Semantic**: facts and chunks, vector-indexed. Each unit carries
  provenance (`source`, `record_id`, `version`, `created_at`) and scope
  (`user_id` and any tenant/agent id).
- **Episodic**: what happened in past runs and how it turned out. The raw
  material self-evolution learns from.
- **Procedural**: agent-authored skills and prompt/guardrail versions. This is
  executable memory; treat it as untrusted code (below).

## Retrieval

- Scope filters (`user_id`, agent id, validity window) go **inside**
  `$vectorSearch` as index-native `filter` fields, never as a `$match` after
  it. Post-filtering leaks across scopes and silently returns fewer results.
- Every filter field is declared as a `filter` type in the vector index
  definition, or the query fails.
- Return provenance with every recalled unit so the UI and logs can show why
  the agent remembered something. For a demo, "why did it do that" is the
  most convincing thing on screen.
- Record the embedding model and dimension next to the index definition.
  Changing either means re-embedding everything.

## Self-evolution

Anything the agent writes that changes its own future behavior (a skill, a
prompt, a guardrail, a tool policy) goes through the proposal → gates → FDE →
versioned promotion loop in `harness-evolution.md`. Memory code never
promotes, overwrites, or deletes a harness version itself.

## Deletion

Deleting a memory must make it unservable immediately, not "after the index
catches up". Mark it deleted and filter on that flag in the vector query, then
remove it.
