---
paths:
  - "**/*.test.ts"
  - "**/*.test.tsx"
  - "**/*.spec.ts"
  - "**/test_*.py"
  - "**/tests/**"
  - "**/conftest.py"
---

# Testing

## Rules

- New behavior ships with tests. A bug fix ships with a regression test that
  **fails before the fix** — write it first and watch it fail.
- Test observable behavior through public interfaces. Tests that assert on
  private internals break on every refactor and protect nothing.
- Mock at I/O boundaries only: network, clock, LLM providers, third-party APIs.
  Never mock the unit under test.
- Deterministic always. No real network, no wall-clock dependence, no reliance
  on test execution order, no sleeps as synchronization.

## Layer-specific

- **`core/` domain logic** — pure unit tests, no emulators, fast. This is where
  most tests should be.
- **MongoDB adapters** — run against the `mongodb/mongodb-atlas-local`
  container (plain `mongod` has no `$vectorSearch`), never a live Atlas cluster. Each test gets its own database and drops it afterward.
- **LLM calls** — never hit the live API in tests. Fixture the response.
  Test the parsing, the error handling, and the safety-block path, not the
  model's output quality; that belongs in `evals/`.
- **Frontend** — test behavior a user can observe. Query by role and label, not
  by test id or class name, wherever the accessible query works.

## Anti-patterns to reject in review

- A test that passes when the implementation is deleted.
- Snapshot tests over large trees, regenerated without reading the diff.
- `try/except` swallowing an assertion.
- Skipped or `xfail` tests without a linked issue explaining the plan.
