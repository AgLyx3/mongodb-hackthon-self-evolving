---
description: Hackathon submission-readiness audit against what the MongoDB NYC hackathon judges on, plus deploy and secret checks.
disable-model-invocation: true
argument-hint: (no arguments)
---

# Submission readiness check

Current dependency surface:

!`ls services/*/pyproject.toml apps/web/package.json 2>/dev/null || echo "(project not scaffolded yet)"`

## Verify each with file:line evidence

1. **MongoDB Atlas is the system of record** on a live request path, and the
   deployed app points at an Atlas cluster, not only a local container.
2. **Atlas Vector Search is used for real.** A vector index definition exists
   in code and a `$vectorSearch` stage runs on a request path. A comment or
   an unused helper does not count.
3. **Agent memory is substantive.** Memory persists across sessions
   (`MongoDBStore` or equivalent), is recalled with scope filters, and visibly
   changes agent behavior. State (checkpointer) alone is not memory.
4. **Self-evolution is real and gated.** Trace one change end to end in the
   database: failure traces → proposal (hypothesis, falsification criterion)
   → gate results (lint, activation beacon, delta vs noise band, replay
   fix/forget) → FDE decision → new content-hashed version → survival counter.
   Then roll it back and confirm the live pointer moved. Delegate to
   `evolution-safety` for the kernel/surface boundary.
5. **Deploy path.** The build succeeds; run it. The public URL loads and the
   primary demo flow runs end to end against deployed infrastructure.
6. **No secrets committed.** Check for `.env`, connection strings, API keys in
   tracked files and git history.
7. **Demo readiness.** The flow can be shown in under three minutes and makes
   memory and evolution visible on screen (what was recalled, what changed,
   and why).

Delegate the database-shape questions to `migration-auditor` if a shape or
index changed today.

## Output

A readiness table: item, status, evidence, what remains. Be blunt. An
optimistic report here costs the submission.
