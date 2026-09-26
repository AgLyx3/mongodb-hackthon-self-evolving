# CLAUDE.md

**mongodb-hackthon-self-evolving**: a self-evolving deployment harness for
forward-deployed engineers (FDEs). The agent runs customer tasks, turns
recurring failures into **proposed, versioned changes to its own harness**
(prompts, skills, tools, control hooks), automated gates screen them, and a
human FDE accepts, edits, or rejects each one. The key metric is **change
survival**: accepted changes that stay live and aren't reverted. MongoDB Atlas
holds the versions, traces, evals, decisions, and memory. <!-- TODO: name the
concrete customer task the demo runs. -->

Research behind the design is in `research/notes/`. The rules distilled from
it are in `.claude/rules/harness-evolution.md`.

**Harness invariants** (details in that rule):
- The agent proposes; only the FDE action promotes. Proposer code has no write
  path to live versions, evals, gates, or limits.
- Versions are immutable and content-hashed; logs are append-only; rollback is
  one pointer change.
- An improvement counts only if it beats the measured noise band on cases the
  proposer never saw, and replay shows what it broke.
- Proposer confidence is never evidence.

Status: greenfield. Nothing is scaffolded yet.

## Hackathon

MongoDB NYC hackathon, "The Harness Engineering & Model Wrangling Hackathon"
(cerebralvalley.ai/e/mongodb-nyc-hackathon).

- **Build day:** Sat 2026-09-26, 9 AM – 10 PM EDT. **Submissions due 10 PM
  EDT** (2026-09-27 02:00 UTC). Scope every decision to that clock.
- **Finalists** record a demo on-site on 09-26 and present live at
  MongoDB.local NYC on 2026-09-30 from 10 AM EST. Top 3 split $15,000.
- **Judged on:** impactful projects built with **MongoDB Atlas, Vector Search,
  and Agentic Memory tooling**. Named examples: agents that rewrite their own
  guardrails, systems that hold context across weeks-long tasks, new
  approaches to persistent agent memory.
- Team size max 4.

## Design rationale: what the judges reward

Judges and their specialities are in `research/judges.md`. Five rules follow
from them. Apply them to every design choice, and say which one a
decision serves when it matters.

1. **Glass box.** Every agent action and every harness change traces to its
   evidence (failure traces), its gate results, and a named FDE decision.
   Tenex, whose SOC does alert triage with forward-deployed engineers, sells
   exactly this. If a change can't be explained on screen, it isn't done.
2. **Rigor over vibes.** Every "improved" claim shows the delta, the noise
   band, and held-out/replay results (Vin Sachidananda, a Stanford NLP PhD).
   Never present an unresolved change as a win.
3. **MongoDB does real work.** Versions, traces, decisions, and memory live in
   Atlas; recall uses `$vectorSearch` with scope filters and returns
   provenance (Joseph Morais, MongoDB evangelist).
4. **Deliberate model wrangling.** A cheap model per task, a stronger model
   only where measured to help, spend capped through OpenRouter (Louis Vichy,
   OpenRouter co-founder; MongoDB Ventures invested in OpenRouter). The $10
   budget is part of the story, not a limitation to hide.
   **A strong model must not make the harness pointless.** Every eval
   reports a strong-model baseline (strong model + base harness) next to the
   evolved harness on the cheap model. The claim to earn: the evolved
   harness matches or beats that baseline at a fraction of the cost, on
   signal the strong model can't recover from a single case (the calibration
   check in `harness-evolution.md` §5). If the strong model solves the cases
   on the base harness, the eval set is wrong, not the harness right: fix the
   cases before claiming anything.
5. **Safe to operate.** Immutable versions, one-step FDE rollback, append-only
   logs, inspectable traces (Andrey Sibirev, Vercel compute and reliability).

Framing for the demo: self-improving steering rules that a human approves,
which is the next step past hand-written agent config files (Brooke Jamieson,
AWS). Expect Dan Zakon (Tenex) to ask whether an analyst would trust it and
whether it reduces false positives; the demo should answer both unprompted.

The public page lists no further hard rules. Attendee-only details may add
some; paste them here if they do.

## Stack

| Layer | Choice | Why |
| --- | --- | --- |
| Database + memory | **MongoDB Atlas** | Required |
| Retrieval | **Atlas Vector Search** (`$vectorSearch`) | Required |
| Embeddings | **Atlas Automated Embedding (Voyage AI)**; fall back to the Voyage API client-side if the preview isn't available on the cluster | Keeps embeddings in sync with no pipeline |
| Agent framework | **LangGraph (Python)** + `langgraph-checkpoint-mongodb` (state) + `langgraph-store-mongodb` (long-term memory) | MongoDB's official agent-memory integration |
| Backend | Python 3.12, FastAPI, `uv` | |
| Frontend | Next.js (App Router) + TypeScript, `pnpm` | |
| LLM access | **OpenRouter** (OpenAI-compatible API). No fixed vendor: the cheapest model that passes each task's eval by default; a stronger model only where measured to help; spend capped at the key. Model IDs come from OpenRouter's catalog, never from memory | "Model wrangling" theme; OpenRouter is a judging partner; $10 total budget |
| Hosting | **Vercel** for web and the FastAPI service | One deploy target; Vercel is a judging partner |
| Local DB | `mongodb/mongodb-atlas-local` Docker image | Supports `$vectorSearch` locally; plain `mongod` does not |

Only the first two rows are mandated. The rest are defaults chosen for the
theme and the one-day clock. Don't swap a layer without asking.

## Commands

<!-- TODO: fill in at scaffold time. Until these are real, the verification loop
     below cannot run and agents will invent commands. -->

| Purpose | Command |
| --- | --- |
| Install | `TODO` |
| Dev | `TODO` |
| Typecheck | `TODO` |
| Lint | `TODO` |
| Test | `TODO` |
| Local MongoDB | `TODO` (`mongodb/mongodb-atlas-local` container) |
| Build | `TODO` |

One package manager per language, never mixed.

## Verification loop

Work is not complete until the loop closes.

1. Make the change.
2. Run typecheck, lint, and the tests covering the touched area.
3. On failure, fix the root cause and re-run. Never paper over a failure by
   deleting the assertion, loosening a type, or adding a skip.
4. For UI changes, drive the browser and compare against the intended result.
5. Show evidence, not assertions: the command run and what it returned. If a
   step was skipped, say so.

## Working style

- When a step doesn't need my input, keep going. Put status notes in the same
  message as your next action. Stop and ask only when you can't continue
  without me, or before anything in the Safety list below.
- Plan first when the change spans several files or the approach is uncertain;
  wait for approval on that plan. If the diff fits in one sentence, skip the
  plan.
- Scope discipline: do what was asked. No opportunistic refactors, no
  reformatting untouched lines, no undiscussed dependencies. Mention unrelated
  problems; don't fix them uninvited.
- Model IDs and SDK calls are never written from memory; check current
  provider docs first.
- Authorization is enforced server-side. Never trust the client.
- New behavior ships with tests; bug fixes ship with a regression test that
  fails before the fix.
- For multi-step work, keep a checklist in `TASKS.md` (current goal, decisions
  approved, remaining items, verification results) and update it as you go. It
  survives compaction; conversation memory does not.
- When compacting, preserve the list of modified files, the commands used to
  verify, and any decisions I approved.
- End every multi-step run with three headings: **Blocked on me**, **Changed**,
  **Found**.

## Safety: ask before doing any of these

These need explicit approval every time, regardless of permission mode:

- `git push`, force-push, or any history rewrite
- Deleting files or directories not created in the current task
- Any deploy
- Writes against a non-local MongoDB (Atlas); any migration or backfill
- Adding, removing, or upgrading a dependency
- Reading, writing, or printing secrets, `.env` files, or connection strings
- Sending repository contents to a third-party service

A MongoDB connection string contains a password; treat it as a secret.
Enforced by `.claude/settings.json` and `.claude/hooks/guard_bash.py`: secret
reads, commits on `main`, and pushes/`rm -rf` prompts. The rule stands where
enforcement doesn't reach.

## Git

Branch per unit of work. Imperative commit subjects, one logical change per
commit. Commit and push only when asked.

## Where the rest of the context lives

Topic-scoped rules in `.claude/rules/` load only when matching files are
touched. Their `paths:` globs assume `apps/web/` + `services/*/`; update them if
the layout differs.

| Rule | Covers |
| --- | --- |
| `backend.md` | Layering, agent tools, async, config, errors |
| `frontend.md` | Design tokens, contracts, defaults to avoid, per-screen reference patterns |
| `database.md` | MongoDB modeling, indexes, writes, migrations |
| `llm-prompts.md` | Prompt files, structured output, evals, cost |
| `harness-evolution.md` | Kernel vs surface, proposal schema, gates, eval splits and noise band, FDE signal, survival, rollback |
| `agent-memory.md` | State vs memory, scoped recall, deletion |
| `claude-api.md` | Claude model behavior, when calling Claude (directly or via OpenRouter) |
| `testing.md` | What to test and how |

## Subagents

- **`check-auditor`**: mutation-tests a new or changed test/check to prove it
  can fail. Run before citing a self-written test as evidence.
- **`migration-auditor`**: audits migrations, backfills, document-shape
  changes, and index changes before they touch a real database.
- **`evolution-safety`**: adversarial review of versioning, gates, promotion,
  rollback, and the proposer's permissions. Required for any diff touching
  the evolution kernel.
- **`ui-critic`**: reviews a built screen against `frontend.md` and its
  reference pattern. Run before calling UI work done.

Before calling a multi-file change done, run `/code-review` on the diff. Act
on findings that affect correctness or the stated requirements; treat the rest
as optional rather than growing defensive code for cases that can't happen.

## Skills

Project playbooks: `/new-agent-tool`, `/new-llm-prompt`, `/submission-check`
(run before submitting).

MongoDB's official skills are vendored under `.claude/skills/`:
`mongodb-schema-design`, `mongodb-search-and-ai` (vector/hybrid search and
index definitions), `mongodb-query-optimizer`, `mongodb-connection`,
`mongodb-mcp-setup`. Pinned versions are in `.claude/skills/VENDORED.md`. Do
not hand-edit them. For Vercel deploys, the `vercel:*` plugin skills apply.

## MCP

`.mcp.json` runs the MongoDB MCP server **read-only**. It reads
`MDB_MCP_CONNECTION_STRING` from the shell environment, so export it before
starting Claude Code; the secret never goes in the repo. Use it to inspect
collections, indexes, and `explain()` output. Writes go through app code or an
approved migration, not MCP. Don't remove `--readOnly` without asking.
