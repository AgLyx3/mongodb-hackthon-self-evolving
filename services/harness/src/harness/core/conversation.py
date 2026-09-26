"""The run as a conversation between its actors. Pure: raw stored docs in, ordered messages out.

Nothing is regenerated; every message is a recorded document (probe, finding, proposal,
gate result, FDE decision, retrospective, lesson, batch report). Order within a round
follows the loop: FDE retro on the previous round's failures, lessons written from it,
investigation, findings, then each proposal thread (proposal, gates, decision,
revisions), then the round's measured result.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel

Actor = Literal["system", "investigator", "tool", "customer", "proposer", "gates", "fde",
                "playbook"]


class Message(BaseModel):
    seq: int
    round: int
    actor: Actor
    kind: str
    text: str
    who: str | None = None
    detail: str | None = None
    sources: list[str] = []
    items: list[str] = []
    status: str | None = None
    ref: str | None = None
    depth: int = 0


def _scope(u: dict[str, Any]) -> str:
    if u.get("kind") == "definition":
        return f"definition of {u.get('field')}"
    cl = (u.get("applies_when") or {}).get("all_of", [])
    return " AND ".join(f"{c['path']} {c['op']} {c['value']}" for c in cl) or "always"


def build(*, probes: list[dict[str, Any]], findings: list[dict[str, Any]],
          proposals: list[dict[str, Any]], gates: dict[str, list[dict[str, Any]]],
          decisions: dict[str, dict[str, Any]], feedback: list[dict[str, Any]],
          lessons: list[dict[str, Any]], reports: list[dict[str, Any]],
          labels: dict[str, str]) -> list[Message]:
    """Order the recorded documents of one run into a conversation.

    gates: proposal id -> gate results in time order (summary rows are skipped).
    decisions: proposal id -> FDE decision. labels: case id -> revealed label.
    """
    out: list[Message] = []

    def say(rnd: int, actor: Actor, kind: str, text: str, **kw: Any) -> None:
        out.append(Message(seq=len(out), round=rnd, actor=actor, kind=kind, text=text, **kw))

    by_round: dict[str, dict[int, list[dict[str, Any]]]] = {
        k: defaultdict(list) for k in ("probes", "findings", "proposals", "lessons")}
    for pr in probes:
        if pr.get("run_tag", "main") == "main":
            by_round["probes"][pr["batch"]].append(pr)
    for f in findings:
        if f.get("run_tag", "main") == "main":
            by_round["findings"][f["batch"]].append(f)
    for p in proposals:
        if not p.get("revision_of"):
            by_round["proposals"][p["batch"]].append(p)
    for le in lessons:
        by_round["lessons"][le["created_batch"]].append(le)
    children = {p["revision_of"]: p for p in proposals if p.get("revision_of")}
    start_fb = {d["batch"]: d for d in feedback if d["phase"] != "final"}
    final_fb = [d for d in feedback if d["phase"] == "final"]
    report = {r["batch"]: r for r in reports}

    rounds = sorted({*report, *start_fb, *(r for g in by_round.values() for r in g)})
    for rnd in rounds:
        if rnd == 0:
            say(0, "system", "round_start", "Start: base harness, no alerts reviewed yet")
        else:
            say(rnd, "system", "round_start",
                f"Discovery round {rnd} · {30 * rnd} alerts reviewed")
        if rnd in start_fb:
            _retro(say, rnd, start_fb[rnd])
        for le in by_round["lessons"][rnd]:
            ok = le["status"] == "active"
            say(rnd, "playbook", "lesson",
                le["text"] if ok else f"Draft lesson rejected by lint: {le.get('lint')}",
                status="active" if ok else "rejected", ref=le["lesson_id"],
                detail=f"from repeated '{le['cause']}' feedback")
        for pr in by_round["probes"][rnd]:
            say(rnd, "investigator", "tool_call", pr["tool"],
                detail=json.dumps(pr["args"]), status=f"cost {pr['cost']}")
            say(rnd, "customer" if pr["tool"] == "ask_customer" else "tool", "tool_result",
                pr["preview"], sources=list(pr["sources"]))
        for f in by_round["findings"][rnd]:
            if f.get("empty"):
                say(rnd, "investigator", "finding", "No finding this round.")
                continue
            say(rnd, "investigator", "finding", f["statement"], detail=f.get("evidence"),
                sources=list(f.get("sources", [])), status=f.get("kind"))
        for p in by_round["proposals"][rnd]:
            _thread(say, rnd, p, children, gates, decisions, labels, 0)
        if rnd in report and report[rnd].get("report_acc") is not None:
            r = report[rnd]
            say(rnd, "system", "round_result",
                f"Report accuracy after round {rnd}: {r['report_acc'] * 100:.1f}%",
                detail=(f"measured on report cases no gate or decision sees; "
                        f"live version {r.get('version')}"), ref=r.get("version"))
    for d in final_fb:
        _retro(say, d["batch"], d)
    return out


def _retro(say: Any, rnd: int, d: dict[str, Any]) -> None:
    when = "after the final round" if d["phase"] == "final" else f"before round {rnd}"
    text = (f"Retrospective {when}: traced {d['explained_cases']} of "
            f"{d['failed_cases']} failed cases back to the agent's method.")
    say(rnd, "fde", "retro", text if d["items"] else text + " No method feedback.",
        who=d.get("fde_id"),
        items=[f"{i['message']} ({i['n_cases']} case(s): {', '.join(i['cases'])})"
               for i in d["items"]])


def _thread(say: Any, rnd: int, p: dict[str, Any], children: dict[str, dict[str, Any]],
            gates: dict[str, list[dict[str, Any]]], decisions: dict[str, dict[str, Any]],
            labels: dict[str, str], depth: int) -> None:
    pid = p.get("proposal_id", p["_id"])
    if p.get("invalid"):
        say(rnd, "proposer", "proposal", "Draft could not be parsed.",
            detail=str(p["invalid"]), ref=pid, depth=depth, status="invalid")
    else:
        u = (p.get("change") or {}).get("add")
        head = u["title"] if u else "Retire a unit"
        items = []
        if u:
            items.append(f"When: {_scope(u)} → {u.get('disposition') or 'definition'}")
            items.append(f"Instruction: {u['text']}")
        items += [f"Hypothesis: {p.get('hypothesis', '')}",
                  f"Falsified if: {p.get('falsification_criterion', '')}"]
        rec = p.get("recalled") or []
        if rec:
            items.append(f"Recalled {len(rec)} past decision(s): " + "; ".join(
                f"{r['proposal_id']} → {r.get('fde_action') or 'stopped at gates'}"
                for r in rec[:3]))
        say(rnd, "proposer", "revision" if depth else "proposal", head, ref=pid, items=items,
            sources=list(p.get("evidence_refs", [])), depth=depth)
    for g in gates.get(pid, []):
        if g["gate"] == "summary":
            continue
        say(rnd, "gates", "gate", g["gate"], detail=g["detail"],
            status="pass" if g["passed"] else "fail", ref=pid, depth=depth)
    d = decisions.get(pid)
    if d:
        auto = str(d.get("fde_id", "")).startswith("auto:")
        items = [f"{cid} (correct: {labels.get(cid, '?')})"
                 for cid in d.get("counterexamples", [])]
        if d["action"] == "edit" and d.get("final_scope"):
            items.append(f"FDE-approved scope: {d['final_scope']}")
        say(rnd, "gates" if auto else "fde", "decision", d["action"],
            who=d.get("fde_id"), detail=d.get("rationale"), status=d.get("reason_tag"),
            items=items, ref=pid, depth=depth)
        if d.get("promoted"):
            say(rnd, "system", "promotion", f"Promoted: live version is now {d.get('version')}",
                ref=d.get("version"), detail=d.get("promoted_unit_id"), depth=depth)
    elif not p.get("invalid"):
        say(rnd, "system", "no_decision", "FDE not consulted: stopped by the gates.",
            ref=pid, depth=depth)
    child = children.get(pid)
    if child:
        _thread(say, rnd, child, children, gates, decisions, labels, depth + 1)
