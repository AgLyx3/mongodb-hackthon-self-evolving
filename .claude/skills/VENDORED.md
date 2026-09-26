# Vendored skills

Copied verbatim from upstream. **Do not hand-edit them**; changes are lost on
refresh. Project-specific guidance belongs in `.claude/rules/` or a
project-authored skill.

| Skill | Upstream | Pinned |
| --- | --- | --- |
| mongodb-schema-design | mongodb/agent-skills `skills/` | `d1d2d86` |
| mongodb-search-and-ai | mongodb/agent-skills `skills/` | `d1d2d86` |
| mongodb-query-optimizer | mongodb/agent-skills `skills/` | `d1d2d86` |
| mongodb-connection | mongodb/agent-skills `skills/` | `d1d2d86` |
| mongodb-mcp-setup | mongodb/agent-skills `skills/` | `d1d2d86` |

Vendored on 2026-09-26. License: Apache-2.0, see `LICENSE.mongodb-agent-skills`.

Not vendored: `mongodb-atlas-stream-processing` (Kafka/S3 pipelines, out of
scope) and `mongodb-natural-language-querying`.

## Refreshing

```sh
git clone --depth 1 https://github.com/mongodb/agent-skills /tmp/mdb-agent-skills
cp -R /tmp/mdb-agent-skills/skills/<name> .claude/skills/
```

Then update the pinned commit above.
