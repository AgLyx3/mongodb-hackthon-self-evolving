# Independent Code Review

When asked to review a diff or perform an independent second-model review, act
as a reviewer of changes authored by another model or contributor. Find
concrete defects before the author acts on them; do not endorse or rewrite the
implementation. These instructions apply to review requests and do not change
ordinary implementation work.

## Review procedure

1. Establish scope from the user's requested base, commit, or diff. If none is
   specified, inspect the current worktree, including staged, unstaged, and
   relevant untracked files. Do not assume `HEAD` contains the whole change,
   especially in a new repository.
2. Read `CLAUDE.md`, then the matching rules under `.claude/rules/` and any
   relevant specialist auditor under `.claude/agents/`. Read only what applies
   to the changed code.
3. Trace changed behavior through realistic inputs and failure paths. Check
   authorization, persistence, concurrency, error handling, compatibility,
   and test coverage as relevant to the diff.
4. Report issues; do not edit files or run mutation tests. Do not execute
   commands that write to a database, contact a service, or incur a charge.
   Use static analysis when exercising a path would have side effects or needs
   unavailable credentials.

## Findings

Include a finding only when the change can cause incorrect behavior, data loss,
security exposure, a broken stated requirement, or a meaningful verification
gap. Order findings by severity (critical, high, medium, low). Each finding
needs a concise title, severity, smallest relevant `path:line` location in the
changed code, a specific triggering input or sequence and observable impact,
and the smallest useful correction.

Do not report style preferences, hypothetical risks without a reachable path,
or issues already present outside the reviewed change. State assumptions and
distinguish proven defects from static concerns that could not be exercised.

Start the response with findings. If none are supported, say `No findings.`
Then list important scope limits or checks that could not be run. Keep change
summaries brief and secondary. Never silently fix a finding; return it to the
author for an independent decision.

## Project review routing

- For changes under `services/**/harness/**`, `services/**/evolution/**`,
  `services/**/agent/**`, `services/**/evals/**`, or `services/**/models/**`,
  read `.claude/rules/harness-evolution.md`. For proposals, gates, eval splits,
  promotion, rollback, or proposer permissions, also apply
  `.claude/agents/evolution-safety.md` as an adversarial checklist.
- For tests and verification scripts, read `.claude/rules/testing.md` and
  inspect what the test actually asserts. The mutation procedure in
  `.claude/agents/check-auditor.md` is a separate, explicitly requested audit,
  not part of ordinary review.
- For database models, queries, indexes, or migrations, read
  `.claude/rules/database.md`. Atlas writes and migrations are out of scope
  unless separately authorized.
- For UI changes, read `.claude/rules/frontend.md`; say visual behavior is
  unverified if it cannot be rendered in the available environment.
- For prompt or provider integration changes, read the matching
  `.claude/rules/llm-prompts.md` or `.claude/rules/claude-api.md`.

Follow the safety rules in `CLAUDE.md`: do not read `.env`, connection strings,
or files under `secrets/` during review, and do not send repository contents to
a third party.

## Claude handoff

From the repository root, Claude can request an independent review through the
Codex CLI:

```sh
codex review --uncommitted "Follow AGENTS.md and CLAUDE.md. Review these changes independently and return findings only; do not edit files."
```

For a committed branch diff, use `codex review --base <branch>` with the same
instructions. Codex CLI must be installed and authenticated in the environment
where Claude runs the command. Run it only when the user requests the
cross-model review; it sends the reviewed context to the configured Codex model
provider, so follow the authorization rule in `CLAUDE.md`.
