---
paths:
  - "**/prompts/**"
  - "**/*prompt*.py"
  - "**/*prompt*.ts"
  - "**/evals/**"
---

# LLM prompts and evaluation

Before writing or changing any model call, check the provider's current docs.
Model IDs and SDK idioms drift faster than training data. Do not write a model
name from memory.

## Where prompts live

Prompts are versioned files under `prompts/`, not string literals inline in
handlers. A prompt is a product artifact: it gets reviewed, diffed, and rolled
back like code.

- One file per prompt, named for the task (`summarize_session.md`).
- Template variables are explicit and documented at the top of the file.
- The file records which model it was tuned against. A prompt tuned on a small
  model does not automatically transfer to a large one.

## Writing prompts

- State the task, the constraints, and the output format. Format instructions
  go last; they are the most likely to be dropped from the middle.
- Prefer **structured output** (response schema) over asking for JSON in prose
  and parsing it. Parsing model prose is a recurring source of production bugs.
- Give the model the context it needs explicitly, with structure. Do not assume
  it can infer structure from a flat text dump.
- Long context goes before the instruction, not after.

## Model selection

- Default to the fast tier for interactive, latency-sensitive features.
- Reserve the large tier for genuinely hard reasoning.
- Never hardcode a model ID in more than one place. One constant, one config.

## Safety and cost

- Never log the full prompt or completion. Log token counts, latency, and a
  request ID.
- Set explicit token limits on every call. An unbounded generation is a cost
  incident.
- Handle refusals, safety blocks, and empty responses explicitly. They are
  normal outcomes, not exception paths to ignore.
- User-supplied or retrieved text reaching a model is untrusted. Treat it as a
  prompt-injection vector.

## Evaluation

Any prompt change that ships needs a before/after on a fixed set of cases in
`evals/`. "It looked better in one manual test" is not evidence. Record the
comparison in the PR.
