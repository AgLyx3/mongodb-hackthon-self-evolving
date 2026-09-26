"""Read models for the FDE review UI. All reads, no writes."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from harness.adapters.mongo.client import app_db, eval_db
from harness.adapters.mongo.store import load_units
from harness.core.units import render_harness


def _clean(d: dict[str, Any]) -> dict[str, Any]:
    d = dict(d)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


async def customers() -> list[dict[str, Any]]:
    out = []
    async for c in app_db()["customers"].find({}):
        c = _clean(c)
        relevance = {s["source_id"]: s for s in c["manifest"]}
        ptr = await app_db()["live_pointers"].find_one({"customer": c["id"]})
        c["live_version"] = ptr["version"] if ptr else None
        c["manifest"] = list(relevance.values())
        out.append(c)
    return out


async def timeline(customer: str) -> dict[str, Any]:
    db = app_db()
    reports = [_clean(r) async for r in db["batch_reports"].find(
        {"customer": customer}).sort("batch", 1)]
    events = [_clean(e) async for e in db["pointer_events"].find(
        {"customer": customer}).sort("at", 1)]
    versions = []
    for e in events:
        v = await db["harness_versions"].find_one({"_id": e["to"]})
        acc = await db["gate_results"].find_one(
            {"proposal_id": e.get("proposal_id"), "gate": {"$in": ["backtest",
                                                                   "backtest_fde_edit"]},
             "passed": True}, sort=[("at", -1)])
        dec = await db["fde_decisions"].find_one({"proposal_id": e.get("proposal_id")})
        versions.append({
            "version": e["to"], "parent": e["from"], "batch": e["batch"], "reason": e["reason"],
            "edge": v["edge"] if v else None, "proposal_id": e.get("proposal_id"),
            "holdout_acc": acc["holdout_acc"] if acc else None,
            "unit_id": dec.get("promoted_unit_id") if dec else None,
            "fde_action": dec.get("action") if dec else None, "at": e["at"]})
    noise = reports[0] if reports else {}
    if versions and noise:
        versions[0]["holdout_acc"] = noise.get("holdout_acc")
    return {"versions": versions, "reports": reports,
            "noise_cases": noise.get("noise_cases"), "noise_accs": noise.get("noise_accs")}


async def harness(customer: str, version: str | None) -> dict[str, Any]:
    db = app_db()
    if version is None:
        ptr = await db["live_pointers"].find_one({"customer": customer})
        version = ptr["version"] if ptr else None
    if version is None:
        return {"version": None, "units": [], "rendered": ""}
    units = await load_units(version)
    return {"version": version, "rendered": render_harness(units),
            "units": [{**u.model_dump(mode="json"), "hash": u.content_hash,
                       "scope": u.applies_when.render() if u.applies_when else None}
                      for u in units]}


async def proposals(customer: str) -> list[dict[str, Any]]:
    db = app_db()
    out = []
    async for p in db["proposals"].find({"customer": customer}).sort("created_at", 1):
        p = _clean(p)
        gates = [_clean(g) async for g in db["gate_results"].find(
            {"proposal_id": p["id"]}).sort("at", 1)]
        dec = await db["fde_decisions"].find_one({"proposal_id": p["id"]})
        p["gates"] = gates
        p["fde"] = _clean(dec) if dec else None
        summary = next((g for g in gates if g["gate"] == "summary"), None)
        p["outcome"] = summary["detail"] if summary else "pending"
        p["promoted"] = bool(dec and dec.get("promoted"))
        p["matched_signal"] = (dec or {}).get("matched_signal") or (summary or {}).get(
            "matched_signal")
        out.append(p)
    return out


async def sources(customer: str) -> dict[str, Any]:
    db = app_db()
    probes: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    async for pr in db["probes"].find({"customer": customer}):
        tag = f"b{pr['batch']}:{pr['run_tag']}"
        for s in pr["sources"] or ["(none)"]:
            probes[tag][s]["cost"] += pr["cost"] / max(1, len(pr["sources"]))
            probes[tag][s]["calls"] += 1
    relevance = {}
    async for s in eval_db()["answer_key"].find({"customer": customer}):
        for loc in s["locations"]:
            relevance[loc] = True
    reports = [r async for r in db["batch_reports"].find({"customer": customer}).sort("batch", 1)]
    return {
        "probes": {t: {s: dict(c) for s, c in v.items()} for t, v in probes.items()},
        "usefulness_by_batch": [{"batch": r["batch"], "usefulness": r.get("usefulness_after", {})}
                                for r in reports],
        "relevant_sources": sorted(relevance),
    }


async def metrics(customer: str) -> dict[str, Any]:
    db, ev = app_db(), eval_db()
    key = [s async for s in ev["answer_key"].find({"customer": customer, "aux": False})]
    decs = [d async for d in db["fde_decisions"].find({"customer": customer})]
    promoted = [d for d in decs if d.get("promoted")]
    ptr = await db["live_pointers"].find_one({"customer": customer})
    live = set((await db["harness_versions"].find_one({"_id": ptr["version"]}))["unit_hashes"]) \
        if ptr else set()
    survived = [d for d in promoted if d.get("promoted_unit_hash") in live]
    found = sorted({d["matched_signal"] for d in promoted if d.get("matched_signal")})
    planted = [s["signal_id"] for s in key]
    by_batch: dict[int, list[float]] = defaultdict(list)
    for d in decs:
        by_batch[d["batch"]].append(d.get("edit_distance", 0.0))
    reports = [r async for r in db["batch_reports"].find({"customer": customer}).sort("batch", 1)]
    decoy = await _decoy_spend(customer)
    n_props = await db["proposals"].count_documents({"customer": customer})
    gate_fail = await db["gate_results"].count_documents(
        {"customer": customer, "gate": "summary", "passed": False})
    spend = await db["llm_spend"].find_one({"_id": "ledger"})
    from harness.config import get_settings  # local: views stay import-light
    strong = [t["correct"] async for t in db["traces"].find(
        {"customer": customer, "tag": "calibration", "model": get_settings().strong_model},
        {"correct": 1})]
    return {
        "strong_baseline": (sum(strong) / len(strong)) if strong else None,
        "planted_signals": planted, "signals_learned": found,
        "signal_recall": len([s for s in found if s in planted]) / len(planted) if planted else 0,
        "holdout_by_batch": [{"batch": r["batch"], "acc": r["holdout_acc"]} for r in reports],
        "noise_cases": reports[0].get("noise_cases") if reports else None,
        "proposals": n_props, "promoted": len(promoted), "survived": len(survived),
        "stopped_or_rejected": gate_fail,
        "fde_actions": dict(Counter(d["action"] for d in decs)),
        "fde_reasons": dict(Counter(d["reason_tag"] for d in decs)),
        "edit_distance_by_batch": {str(b): round(sum(v) / len(v), 3)
                                   for b, v in sorted(by_batch.items())},
        "decoy_spend": decoy,
        "spent_usd_total": round(float(spend["usd"]), 3) if spend else 0.0,
    }


async def _decoy_spend(customer: str) -> dict[str, Any]:
    ev, db = eval_db(), app_db()
    relevant: set[str] = set()
    async for s in ev["answer_key"].find({"customer": customer}):
        relevant.update(s["locations"])
    out: dict[str, dict[str, float]] = {}
    async for pr in db["probes"].find({"customer": customer}):
        tag = f"b{pr['batch']}:{pr['run_tag']}"
        o = out.setdefault(tag, {"total": 0.0, "irrelevant": 0.0})
        share = pr["cost"] / max(1, len(pr["sources"]))
        for s in pr["sources"]:
            o["total"] += share
            if s not in relevant:
                o["irrelevant"] += share
    return {k: {**v, "irrelevant_share": round(v["irrelevant"] / v["total"], 3)
                if v["total"] else 0.0} for k, v in sorted(out.items())}
