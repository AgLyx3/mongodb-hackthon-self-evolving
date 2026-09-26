---
paths:
  - "services/**/*.py"
  - "services/**/pyproject.toml"
  - "services/**/Dockerfile"
---

# Backend: services/

## Layering

Keep three layers distinct and do not let them leak:

- **Transport** (`api/`): routers. Parse, validate, authorize, return.
  No business logic, no direct database calls, no LLM calls.
- **Domain** (`core/`): business logic. Pure Python. No web-framework imports,
  no database driver imports. This is the layer that must be unit-testable
  without any network.
- **Adapters** (`adapters/`): MongoDB, LLM provider, agent runtime. Thin
  wrappers behind protocols the domain defines.

If a change requires importing the web framework into `core/`, the design is
wrong.

## Agent specifics

- Agents, tools, and clients (including the MongoDB client) are constructed once
  at module scope and reused, not rebuilt per request.
- Every tool has a precise docstring; the model routes on it. A vague docstring
  is a functional bug, not a style issue.
- Tools validate their own inputs and return structured errors. Never let a tool
  raise an unhandled exception into the agent loop.
- Long-running agent work does not block the HTTP response. Stream, or hand off
  to a background task with a status the client can poll or subscribe to.

## Conventions

- Type hints on every function signature. `mypy` clean.
- Pydantic models for all request/response bodies and all stored documents.
- `async def` for anything touching I/O. Never call a blocking client inside an
  async handler; use the async MongoDB driver.
- Structured logging to stdout. Never log user content or PII.
- Configuration comes from environment variables, read once into a settings
  object. No `os.environ` scattered through the codebase.

## Errors

Raise domain exceptions from `core/`, translate to HTTP status codes at the
transport boundary. Never return a 200 with an error body.
