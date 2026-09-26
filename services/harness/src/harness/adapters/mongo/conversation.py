"""Read model for the conversation view: loads the current run's documents. Reads only."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from harness.adapters.mongo.client import app_db, eval_db
from harness.core.conversation import Message, build


async def conversation(customer: str) -> dict[str, Any]:
    db, ev = app_db(), eval_db()
    q = {"customer": customer}
    run = await db["runs"].find_one(q, sort=[("started_at", -1)])
    run_id = run["_id"] if run else None
    proposals = [p async for p in db["proposals"].find(q).sort("created_at", 1)]
    pids = [p.get("proposal_id", p["_id"]) for p in proposals]
    private: dict[tuple[str, str], str] = {}
    async for g in ev["gate_private"].find({"proposal_id": {"$in": pids}}).sort("at", 1):
        if g.get("detail"):
            private[(g["proposal_id"], g["gate"])] = g["detail"]
    gates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    async for g in db["gate_results"].find({"proposal_id": {"$in": pids}}).sort("at", 1):
        g["detail"] = private.get((g["proposal_id"], g["gate"]), g["detail"])
        gates[g["proposal_id"]].append(g)
    decisions = {d["proposal_id"]: d async for d in db["fde_decisions"].find(
        {"proposal_id": {"$in": pids}})}
    cases = sorted({c for d in decisions.values() for c in d.get("counterexamples", [])})
    labels = {o["case_id"]: o["label"] async for o in db["outcomes"].find(
        {"case_id": {"$in": cases}})}
    messages: list[Message] = build(
        probes=[p async for p in db["probes"].find(q).sort("_id", 1)],
        findings=[f async for f in db["findings"].find(q).sort("_id", 1)],
        proposals=proposals, gates=gates, decisions=decisions,
        feedback=[d async for d in db["fde_feedback"].find(
            {**q, "run_id": run_id}).sort("batch", 1)],
        lessons=[x async for x in db["method_lessons"].find(
            {**q, "run_id": run_id}).sort("created_batch", 1)],
        reports=[r async for r in ev["batch_reports"].find(q).sort("batch", 1)],
        labels=labels)
    return {
        "run_id": run_id,
        "fde_mode": run.get("fde_mode") if run else None,
        "status": run.get("status") if run else None,
        "runtime_model": run.get("runtime_model") if run else None,
        "messages": [m.model_dump() for m in messages],
    }
