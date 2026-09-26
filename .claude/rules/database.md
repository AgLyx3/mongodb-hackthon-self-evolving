---
paths:
  - "services/**/adapters/mongo/**"
  - "services/**/models/**"
  - "**/migrations/**"
  - "**/indexes/**"
---

# Data: MongoDB

## Modeling

- Design for the query you actually run. Embed what is read together; reference
  what grows independently. Write down why in a comment when you denormalize.
- Every collection's document shape is a Pydantic model in `models/`. The model
  is the schema; there is no other source of truth.
- Do not store an unbounded array in a document. Anything that grows without
  limit (history, logs, events) goes in its own collection. The 16 MB document
  limit is a hard ceiling.
- Store timestamps as UTC `datetime`, set server-side, never from client clocks.

## Queries and indexes

- Every query on a hot path has a supporting index. Check with `explain()`; a
  `COLLSCAN` on a hot path is a defect.
- Indexes are declared in code and created idempotently at startup or by a
  migration, not by hand in the Atlas UI.
- Vector and full-text search indexes (Atlas Search) are also declared in code,
  with the embedding model and dimension recorded next to the definition.
  Changing the embedding model means re-embedding; plan it as a migration.
  Read the vendored `mongodb-search-and-ai` skill before writing one.
- Search indexes build asynchronously. Code and tests that create one must
  wait until it is queryable; a `$vectorSearch` against a building index
  returns nothing, not an error.

## Writes and consistency

- A read-modify-write on shared state uses an atomic update operator (`$set`,
  `$inc`, `$push`, `findOneAndUpdate`) or a transaction. A read, then a full
  `replace_one`, is a lost-update bug waiting to happen.
- Multi-document changes that must agree go in a transaction.
- Never build a query filter from unvalidated user input; operator injection
  (`{"$ne": null}`) is real.

## Migrations

MongoDB is schemaless, so migrations are code. Any change to a document shape
needs a written plan for existing documents: backfill script, tolerant reads
during rollout, or an explicit `schema_version` field. Never ship a shape change
that assumes all documents already have the new field.
