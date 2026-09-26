---
description: Add a new tool to the agent, wired correctly with validation, structured errors, and tests. Use when adding a capability the agent can invoke.
argument-hint: <tool-name and what it should do>
---

# Add an agent tool

## Steps

1. **Confirm the tool is warranted.** A tool is for something the model cannot
   do from context alone: reading stored state, calling an external service,
   performing a deterministic transform. If the model can already do it with the
   context it has, adding a tool makes routing worse, not better. Say so and stop.

2. **Write the domain function first**, in `core/`, as a plain typed function
   with no agent-framework imports. It must be unit-testable with no network.

3. **Write its tests before wiring it up.** Cover the happy path, invalid input,
   and the failure of whatever it depends on. Run them; watch them pass.

4. **Wrap it as a tool** in `adapters/agent/tools/`. The wrapper:
   - Has a **precise docstring**. The model routes on this text, so vague
     wording is a functional bug. State what the tool does, when to use it, and
     what each parameter means.
   - Declares fully typed parameters with a Pydantic schema.
   - Validates inputs and returns a structured error object on bad input. It
     never raises into the agent loop.
   - Does not log user content.

5. **Register it** on the agent constructed at module scope. Do not construct
   agents per request.

6. **Add a routing test**: given a representative user request, assert the agent
   selects this tool. Tool-routing regressions are invisible without this.

7. **Run** the backend typecheck and test suite. Report actual output.

## Reject these

- A tool that wraps another tool with no added logic.
- A tool taking a free-text `query` parameter that the implementation then
  parses. Take structured parameters.
- A tool that can mutate shared state without an atomic update or transaction.
