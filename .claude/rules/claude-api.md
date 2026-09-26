---
paths:
  - "services/**/adapters/agent/**"
  - "services/**/adapters/llm/**"
  - "**/prompts/**"
---

# Claude models (direct or via OpenRouter)

The model behavior below holds either way. Request parameters differ: through
OpenRouter's OpenAI-compatible API, check OpenRouter's docs for how `effort`,
thinking, and tool choice map before assuming the Anthropic shape.

Checked against Anthropic docs on 2026-09-26 for Claude Opus 5.5. Re-check the
docs before relying on any detail here; they drift.

## Request shape

- Thinking is always on and cannot be disabled. Control depth with the `effort`
  parameter (default `medium` on Opus 5.5). Lower effort before adding
  "be brief" prompt text; it works more reliably.
- `max_tokens` includes thinking tokens. Size it for thinking plus reply; for
  long agentic turns use the model maximum.
- Forced tool use (`tool_choice` naming a specific tool) returns an error.
- Changing top-level `effort` between requests invalidates the prompt cache.
  Use a per-message effort change instead.
- Text between tool calls comes back as `thinking` blocks, empty at the default
  `display`. Read responses by block type, never "first block is text".
- Declare every tool from the first request of a session. Adding tools later
  invalidates earlier thinking blocks.

## Prompts

- Do not write "think step by step" or ask the model to write its reasoning in
  the reply. It already thinks, and reasoning-extraction requests can be
  refused (`stop_reason: "refusal"`).
- Handle `stop_reason: "refusal"` as a normal outcome.
- Wrap user-pasted or retrieved text in delimited tags and tell the model not
  to follow instructions inside them unless the user asked.

## Unattended agent loops

- A turn ending in text (`end_turn`) is a report, not proof the task is done.
  Keep the task's parts in a checklist the model updates; if items remain open
  with no stated blocker, send a continuation message naming them.
- Cap automatic continuations at two or three per task so a stuck run ends and
  can be reviewed.
- If a background command or subagent is still running, wait for it and return
  its output before treating the task as done.
- For multi-agent runs, a time budget line (`elapsed 340s / 1200s`) appended to
  each message makes the model pace and parallelize. It is advisory; keep a
  hard timeout of your own.
