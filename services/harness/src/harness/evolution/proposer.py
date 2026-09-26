"""Proposer: turns findings into at most N single-unit proposals.

Writes ONLY through the proposer DB user (insert into `proposals`), so it
cannot promote anything even by mistake. Recalls same-customer past proposals
and FDE decisions via Atlas Vector Search (decision 5).
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from harness.adapters.llm.openrouter import structured
from harness.adapters.mongo.client import proposer_db
from harness.adapters.mongo.indexes import PROPOSALS_INDEX
from harness.config import get_settings
from harness.core.conditions import Clause, Condition
from harness.core.kernel import Change, Proposal
from harness.core.units import Unit, render_harness
from harness.evolution.investigator import Finding, FindingClause
from harness.evolution.tools import parse_value

PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "proposer_system.md"


class Draft(BaseModel):
    action: Literal["add", "supersede", "retire"]
    target_unit_id: str = Field(description="for supersede/retire: existing unit id; else ''")
    kind: Literal["rule", "definition"]
    unit_slug: str = Field(description="short snake_case name for the new unit")
    title: str
    text: str = Field(description="instruction the triage agent will read")
    field: str = Field(description="definition: field it explains; rule: ''")
    clauses: list[FindingClause]
    disposition: Literal["close_false_positive", "request_info", "escalate", "none"]
    hypothesis: str
    falsification_criterion: str
    evidence_sources: list[str]


class Drafts(BaseModel):
    proposals: list[Draft]


def _findings_text(findings: list[Finding]) -> str:
    out = []
    for i, f in enumerate(findings, 1):
        cl = " AND ".join(f"{c.path} {c.op} {c.value}" for c in f.clauses)
        out.append(f"{i}. [{f.kind}] {f.statement}\n   field={f.field or '-'} scope={cl or '-'} "
                   f"disposition={f.disposition} sources={f.sources}\n   evidence: {f.evidence}")
    return "\n".join(out) or "(none)"


async def recall(customer: str, findings: list[Finding], k: int = 5) -> list[dict[str, Any]]:
    """Same-customer past proposals most similar to these findings, with FDE outcomes."""
    db = proposer_db()
    if not findings or await db["proposals"].count_documents({"customer": customer}) == 0:
        return []
    query = " ".join(f.statement for f in findings)[:2000]
    pipe = [{"$vectorSearch": {"index": PROPOSALS_INDEX, "path": "summary", "query": query,
                               "filter": {"customer": customer}, "numCandidates": 50,
                               "limit": k}},
            {"$project": {"_id": 1, "summary": 1, "batch": 1,
                          "score": {"$meta": "vectorSearchScore"}}}]
    try:
        hits = [d async for d in await db["proposals"].aggregate(pipe)]
    except Exception:  # noqa: BLE001 - index may still be syncing; recall is best-effort
        return []
    decisions = {d["proposal_id"]: d async for d in db["fde_decisions"].find(
        {"proposal_id": {"$in": [h["_id"] for h in hits]}})}
    gates = {g["proposal_id"]: g async for g in db["gate_results"].find(
        {"proposal_id": {"$in": [h["_id"] for h in hits]}, "gate": "summary"})}
    out = []
    for h in hits:
        d = decisions.get(h["_id"])
        g = gates.get(h["_id"])
        out.append({"proposal_id": h["_id"], "summary": h["summary"], "batch": h["batch"],
                    "score": round(h["score"], 3),
                    "gate": g["detail"] if g else None,
                    "fde_action": d["action"] if d else None,
                    "fde_reason": d["reason_tag"] if d else None,
                    "fde_rationale": d["rationale"] if d else None,
                    "fde_final_scope": d.get("final_scope") if d else None})
    return out


def _recalled_text(rec: list[dict[str, Any]]) -> str:
    if not rec:
        return "(no past proposals yet)"
    lines = []
    for r in rec:
        verdict = (f"FDE {r['fde_action']} ({r['fde_reason']}): {r['fde_rationale']}"
                   if r["fde_action"] else f"stopped at gates: {r['gate']}")
        scope = f"; FDE-approved scope: {r['fde_final_scope']}" if r.get("fde_final_scope") else ""
        lines.append(f"- batch {r['batch']}: {r['summary']}\n  -> {verdict}{scope}")
    return "\n".join(lines)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", s.lower()).strip("_")[:40] or "unit"


def draft_to_change(customer: str, d: Draft, live: list[Unit]) -> Change:
    by_id = {u.unit_id: u for u in live}
    retire = None
    if d.action in ("supersede", "retire"):
        target = by_id.get(d.target_unit_id)
        if target is None:
            raise ValueError(f"unknown target unit {d.target_unit_id}")
        retire = target.content_hash
    if d.action == "retire":
        return Change(retire_hash=retire)
    cond = None
    if d.kind == "rule":
        cond = Condition(all_of=tuple(Clause(path=c.path, op=c.op, value=parse_value(c.value))
                                      for c in d.clauses))
    unit = Unit(
        unit_id=f"{customer}.{d.kind}.{_slug(d.unit_slug)}", kind=d.kind, layer="truth",
        title=d.title, text=d.text, applies_when=cond,
        disposition=None if d.disposition == "none" or d.kind != "rule" else d.disposition,
        field=d.field or None if d.kind == "definition" else None,
        supersedes=retire, origin="proposal")
    return Change(add=unit, retire_hash=retire)


def summarize(p: Proposal) -> str:
    ch = p.change
    if ch.add is None:
        return f"retire unit {ch.retire_hash}: {p.hypothesis}"
    u = ch.add
    scope = u.applies_when.render() if u.applies_when else f"field {u.field}"
    return f"{u.kind} '{u.title}' when {scope} -> {u.disposition or 'definition'}. {u.text}"


async def propose(
    *, customer: str, batch: int, parent_version: str, live: list[Unit],
    findings: list[Finding], max_proposals: int = 3, recall_enabled: bool = True,
    persist: bool = True, targets: str = "(none)", playbook: str = "(no lessons yet)",
) -> tuple[list[Proposal], list[dict[str, Any]]]:
    """recall_enabled=False and persist=False give the feedback-uptake ablation:
    same findings, no memory of past FDE decisions, nothing written."""
    s = get_settings()
    recalled = await recall(customer, findings) if recall_enabled else []
    system = PROMPT.read_text().split("-->", 1)[1].strip().format(
        customer=customer, harness=render_harness(live), findings=_findings_text(findings),
        recalled=_recalled_text(recalled), max_proposals=max_proposals,
        targets=targets, playbook=playbook)
    drafts, _, _ = await structured(model=s.proposer_model, system=system, schema=Drafts,
                                    user="Write the proposals.", max_tokens=2500,
                                    purpose="propose")
    out: list[Proposal] = []
    db = proposer_db()
    for d in drafts.proposals[:max_proposals]:
        pid = f"{customer}-b{batch}-{'' if persist else 'norecall-'}{uuid.uuid4().hex[:6]}"
        try:
            change = draft_to_change(customer, d, live)
        except (ValueError, Exception) as e:  # noqa: BLE001 - invalid drafts are logged
            if not persist:
                continue
            await db["proposals"].insert_one({
                "_id": pid, "customer": customer, "batch": batch, "invalid": str(e)[:200],
                "summary": f"invalid draft: {d.title}", "created_at": datetime.now(UTC)})
            continue
        p = Proposal(proposal_id=pid, customer=customer, batch=batch,
                     parent_version=parent_version, change=change, hypothesis=d.hypothesis,
                     falsification_criterion=d.falsification_criterion,
                     evidence_refs=tuple(d.evidence_sources),
                     recalled_proposals=tuple(r["proposal_id"] for r in recalled))
        if persist:
            await db["proposals"].insert_one({
                "_id": pid, **p.model_dump(mode="json"), "summary": summarize(p),
                "recalled": recalled, "created_at": datetime.now(UTC)})
        out.append(p)
    return out, recalled


REVISE_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "proposer_revise.md"


async def revise(
    *, original: Proposal, feedback: str, counterexamples: list[dict[str, Any]],
    live: list[Unit], parent_version: str,
) -> Proposal | None:
    """One revision attempt after hint-only FDE feedback. Returns None if unusable."""
    s = get_settings()
    import json

    ce = "\n".join(f"- {c['case_id']}: correct = {c['label']}; record: {json.dumps(c['record'])}"
                   for c in counterexamples) or "(none given)"
    system = REVISE_PROMPT.read_text().split("-->", 1)[1].strip().format(
        customer=original.customer, harness=render_harness(live), original=summarize(original),
        feedback=feedback, counterexamples=ce)
    try:
        drafts, _, _ = await structured(model=s.proposer_model, system=system, schema=Drafts,
                                        user="Write the revised proposal.", max_tokens=2000,
                                        purpose="revise")
    except Exception:  # noqa: BLE001 - a failed revision is simply no revision
        return None
    if not drafts.proposals:
        return None
    d = drafts.proposals[0]
    try:
        change = draft_to_change(original.customer, d, live)
    except Exception:  # noqa: BLE001
        return None
    pid = f"{original.proposal_id}-r1"
    p = Proposal(proposal_id=pid, customer=original.customer, batch=original.batch,
                 parent_version=parent_version, change=change, hypothesis=d.hypothesis,
                 falsification_criterion=d.falsification_criterion,
                 evidence_refs=tuple(d.evidence_sources) or original.evidence_refs,
                 recalled_proposals=original.recalled_proposals)
    await proposer_db()["proposals"].insert_one({
        "_id": pid, **p.model_dump(mode="json"), "summary": summarize(p),
        "revision_of": original.proposal_id, "fde_feedback": feedback,
        "counterexamples": [c["case_id"] for c in counterexamples],
        "created_at": datetime.now(UTC)})
    return p
