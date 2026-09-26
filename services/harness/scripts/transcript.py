"""Render the agent <-> simulated-FDE exchange of the latest run as a Markdown transcript.

Reads what was actually recorded (probes, findings, proposals, gates, FDE decisions,
revisions). Nothing is regenerated. Writes research/transcripts/<customer>.md.
"""

import asyncio
import json
import sys
from typing import Any

from harness.adapters.mongo.client import app_db, eval_db
from harness.config import REPO_ROOT


def _scope(u: dict[str, Any] | None) -> str:
    if not u:
        return "(retire)"
    if u.get("kind") == "definition":
        return f"definition of `{u.get('field')}`"
    cl = (u.get("applies_when") or {}).get("all_of", [])
    return " AND ".join(f"`{c['path']} {c['op']} {c['value']!r}`" for c in cl) + \
        f" → **{u.get('disposition')}**"


class _View:
    """Reads live collections, or archive_<coll> filtered by run_id for past runs."""

    def __init__(self, db: Any, run_id: str | None) -> None:
        self.db, self.run_id = db, run_id

    def __getitem__(self, coll: str) -> Any:
        if self.run_id is None or coll in ("cases", "customers"):
            return self.db[coll]
        return _Filtered(self.db[f"archive_{coll}"], {"run_id": self.run_id})


class _Filtered:
    def __init__(self, coll: Any, extra: dict[str, Any]) -> None:
        self.coll, self.extra = coll, extra

    def find(self, q: dict[str, Any] | None = None, *a: Any, **k: Any) -> Any:
        return self.coll.find({**(q or {}), **self.extra}, *a, **k)

    async def find_one(self, q: dict[str, Any] | None = None, *a: Any, **k: Any) -> Any:
        q = dict(q or {})
        if "proposal_id" in q:  # archived docs keep original ids in orig_id / fields
            pass
        return await self.coll.find_one({**q, **self.extra}, *a, **k)


async def main(customer: str, run_id: str | None = None) -> str:
    db, ev = _View(app_db(), run_id), _View(eval_db(), run_id)
    lines = [f"# Transcript: {customer}", ""]
    ladder = [r async for r in eval_db()["ladder"].find(
        {"customer": customer, **({"run_id": run_id} if run_id else {})}).sort("at", -1)]
    if ladder:
        r = ladder[0]
        lines += [f"Latest run: FDE mode **{r['mode']}**, noise {r['noise']}, "
                  f"report accuracy by round {r['report_by_round']}", ""]
    lines += ["Actors: **Investigator** and **Proposer** (LLM agents, openai/gpt-5.6-luna), "
              "**Gates** (code), **FDE** (`sim-fde:jordan`, a deterministic simulated reviewer; "
              "it never calls an LLM), **Customer contact** (fixed answer table).", ""]
    rounds = sorted({p["batch"] async for p in db["probes"].find({"customer": customer})})
    for rnd in rounds:
        lines += [f"## Discovery round {rnd} ({30 * rnd} alerts reviewed)", "",
                  "### Investigation", ""]
        async for pr in db["probes"].find({"customer": customer, "batch": rnd,
                                           "run_tag": "main"}).sort("_id", 1):
            args = json.dumps(pr["args"])[:200]
            lines.append(f"- **Investigator → {pr['tool']}** {args}")
            who = "Customer contact" if pr["tool"] == "ask_customer" else "Tool"
            lines.append(f"  - *{who}* ({', '.join(pr['sources']) or 'nothing'}): "
                         f"{pr['preview'][:260]}")
        lines += ["", "### Findings", ""]
        async for f in db["findings"].find({"customer": customer, "batch": rnd,
                                            "run_tag": "main"}):
            if f.get("empty"):
                lines.append("- (none)")
                continue
            lines.append(f"- [{f['kind']}] {f['statement']}  \n  evidence: {f['evidence']}  "
                         f"\n  sources: {f['sources']}")
        lines += ["", "### Proposals and review", ""]
        async for p in db["proposals"].find({"customer": customer, "batch": rnd,
                                             "revision_of": {"$exists": False}}
                                            ).sort("created_at", 1):
            await _thread(p, db, ev, lines)
    out = "\n".join(lines) + "\n"
    path = REPO_ROOT / "research" / "transcripts" / f"{run_id or customer}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(out)
    return str(path)


async def _thread(p: dict[str, Any], db: Any, ev: Any, lines: list[str], depth: int = 0) -> None:
    ind = "  " * depth
    pid = p.get("orig_id", p["_id"])  # archived runs prefix _id with the run id
    if p.get("invalid"):
        lines += [f"{ind}**Proposer:** (draft could not be parsed: {p['invalid']})", ""]
        return
    u = (p.get("change") or {}).get("add")
    head = "Proposer (revision)" if depth else "Proposer"
    lines += [f"{ind}**{head}** `{p['_id']}`: {u['title'] if u else 'retire a unit'}",
              f"{ind}> scope: {_scope(u)}"]
    if u:
        lines.append(f"{ind}> instruction for the triage agent: {u['text']}")
    lines += [f"{ind}> hypothesis: {p.get('hypothesis', '')}",
              f"{ind}> falsified if: {p.get('falsification_criterion', '')}",
              f"{ind}> evidence sources: {', '.join(p.get('evidence_refs', []))}"]
    rec = p.get("recalled") or []
    if rec:
        lines.append(f"{ind}> recalled {len(rec)} past decision(s): " + "; ".join(
            f"{r['proposal_id']} → {r.get('fde_action') or 'stopped at gates'}" for r in rec[:3]))
    lines.append("")
    async for g in db["gate_results"].find({"proposal_id": pid}).sort("at", 1):
        if g["gate"] in ("summary",):
            continue
        priv = await ev["gate_private"].find_one({"proposal_id": pid, "gate": g["gate"]})
        detail = (priv or {}).get("detail") or g["detail"]
        lines.append(f"{ind}- **Gates · {g['gate']}:** {'pass' if g['passed'] else 'FAIL'}: "
                     f"{detail}")
    d = await db["fde_decisions"].find_one({"proposal_id": pid})
    if d:
        lines += ["", f"{ind}**FDE** ({d.get('fde_id', 'sim-fde:jordan')}): *{d['action']}* "
                  f"[{d['reason_tag']}]", f"{ind}> {d['rationale']}"]
        for cid in d.get("counterexamples", []):
            c = await app_db()["cases"].find_one({"_id": cid})
            lab = await db["outcomes"].find_one({"case_id": cid})
            lines.append(f"{ind}> - `{cid}` (correct: {lab['label'] if lab else '?'}): "
                         f"`{json.dumps(c['record']) if c else ''}`")
        if d.get("final_scope") and d["action"] == "edit":
            lines.append(f"{ind}> FDE-approved scope: {d['final_scope']}")
        if d.get("revision_distance") is not None:
            lines.append(f"{ind}> (revision moved {d['revision_distance']:.2f} from the original)")
        lines.append(f"{ind}> outcome: {'**promoted**' if d.get('promoted') else 'not promoted'}")
    elif not p.get("invalid"):
        lines.append(f"{ind}**FDE:** not consulted (stopped by the gates).")
    lines.append("")
    child = await db["proposals"].find_one({"revision_of": pid})
    if child:
        await _thread(child, db, ev, lines, depth + 1)


if __name__ == "__main__":
    print(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "bank",
                           sys.argv[2] if len(sys.argv) > 2 else None)))
