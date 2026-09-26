---
description: Create or change a versioned LLM prompt with structured output and an eval comparison. Use when adding an AI feature or tuning existing prompt behavior.
argument-hint: <prompt name and the task it performs>
---

# Add or change an LLM prompt

**Check the provider's current docs before writing any model call.** Do not
write a model name from memory.

## Steps

1. **Create the prompt file** at `prompts/<name>.md`. It records:
   - The task and constraints, instructions last.
   - Template variables, each documented.
   - The model it is tuned against, and why that tier.

2. **Define a response schema.** Use structured output. Do not ask for JSON in
   prose and parse the result.

3. **Wire the call** with an explicit token limit, and handle the paths that are
   normal outcomes rather than exceptions: refusal/safety block, empty response,
   truncation at the token limit.

4. **Add eval cases** in `evals/<name>/`. At minimum: a typical input, an
   empty/degenerate input, a very large input, and one adversarial case (prompt
   injection in user-supplied or retrieved content).

5. **Run the before/after comparison** if changing an existing prompt. Record
   the result. "Looked better in one manual test" is not evidence and does not
   ship.

6. **Verify no logging of prompt or completion bodies.** Log token counts,
   latency, request ID only.

## Output

Report the eval comparison as a table, and state plainly if the change is a
regression on any case.
