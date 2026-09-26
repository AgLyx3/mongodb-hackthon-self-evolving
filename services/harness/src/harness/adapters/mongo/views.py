"""Read models for the FDE review UI. All reads, no writes."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from harness.adapters.mongo.client import app_db, eval_db
from harness.adapters.mongo.store import load_units
from harness.config import get_settings
from harness.core.units import render_harness


def _ptr_id(customer: str) -> str:
    return f"{customer}|{get_settings().runtime_model}"


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
        ptr = await app_db()["live_pointers"].find_one({"_id": _ptr_id(c["id"])})
        c["live_version"] = ptr["version"] if ptr else None
        c["manifest"] = list(relevance.values())
        out.append(c)
    return out


async def timeline(customer: str) -> dict[str, Any]:
    db, ev = app_db(), eval_db()
    reports = [_clean(r) async for r in ev["batch_reports"].find(
        {"customer": customer}).sort("batch", 1)]
    events = [_clean(e) async for e in db["pointer_events"].find(
        {"customer": customer}).sort("at", 1)]
    scores = {r["version"]: r["acc"] async for r in ev["report_scores"].find(
        {"customer": customer})}
    versions = []
    for e in events:
        dec = await db["fde_decisions"].find_one({"proposal_id": e.get("proposal_id")})
        versions.append({
            "version": e["to"], "parent": e["from"], "batch": e["batch"], "reason": e["reason"],
            "edge": e.get("edge"), "proposal_id": e.get("proposal_id"),
            "holdout_acc": scores.get(e["to"]),
            "unit_id": dec.get("promoted_unit_id") if dec else None,
            "fde_action": dec.get("action") if dec else None, "at": e["at"]})
    noise = reports[0] if reports else {}
    return {"versions": versions, "reports": reports,
            "noise_cases": noise.get("noise_cases"), "noise_accs": noise.get("noise_accs")}


async def harness(customer: str, version: str | None) -> dict[str, Any]:
    db = app_db()
    if version is None:
        ptr = await db["live_pointers"].find_one({"_id": _ptr_id(customer)})
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
        priv = {(g["gate"], str(g["at"])[:19]): g async for g in eval_db()["gate_private"].find(
            {"proposal_id": p["id"]})}
        for g in gates:
            extra = priv.get((g["gate"], g["at"][:19]))
            if extra and extra.get("detail"):
                g["detail"] = extra["detail"]
        dec = await db["fde_decisions"].find_one({"proposal_id": p["id"]})
        match = await eval_db()["fde_matches"].find_one({"proposal_id": p["id"]})
        p["gates"] = gates
        p["fde"] = _clean(dec) if dec else None
        if p["fde"] is not None and not p["fde"].get("fde_id"):
            # Decisions recorded before fde_id existed were all made by the simulated FDE.
            p["fde"]["fde_id"] = "sim-fde:jordan (pre-field)"
        summary = next((g for g in gates if g["gate"] == "summary"), None)
        p["outcome"] = summary["detail"] if summary else "pending"
        p["promoted"] = bool(dec and dec.get("promoted"))
        p["matched_signal"] = match["signal"] if match else None
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
    reports = [r async for r in eval_db()["batch_reports"].find(
        {"customer": customer}).sort("batch", 1)]
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
    ptr = await db["live_pointers"].find_one({"_id": _ptr_id(customer)})
    v = await db["harness_versions"].find_one({"_id": ptr["version"]}) if ptr else None
    live = set(v["unit_hashes"]) if v else set()
    matches = {m["proposal_id"]: m["signal"] async for m in ev["fde_matches"].find(
        {"customer": customer})}
    survived = [d for d in promoted if d.get("promoted_unit_hash") in live]
    planted = [s["signal_id"] for s in key]
    # A signal counts as learned only if a unit for it is live now.
    found = sorted({matches.get(d["proposal_id"]) for d in survived} & set(planted))
    edits: dict[int, list[float]] = defaultdict(list)
    for d in decs:
        if d["action"] == "edit":
            edits[d["batch"]].append(d.get("edit_distance", 0.0))
    reports = [r async for r in ev["batch_reports"].find({"customer": customer}).sort("batch", 1)]
    n_props = await db["proposals"].count_documents({"customer": customer})
    gate_fail = await db["gate_results"].count_documents(
        {"customer": customer, "gate": "summary", "passed": False})
    spend = await db["llm_spend"].find_one({"_id": "ledger"})
    comp = await db["comparisons"].find_one({"_id": customer})
    strong = next((r["acc"] for r in (comp or {}).get("rows", [])
                   if r["harness"] == "base" and r["role"] == "strong"), None)
    # Per discovery round: what was learned, and at what investigation cost.
    probes: dict[str, dict[str, float]] = defaultdict(lambda: {"units": 0.0, "decoy": 0.0})
    relevant: set[str] = set()
    async for sig in ev["answer_key"].find({"customer": customer}):
        relevant.update(sig["locations"])
    async for pr in db["probes"].find({"customer": customer}):
        tag = f"{pr['batch']}:{pr['run_tag']}"
        probes[tag]["units"] += pr["cost"]
        srcs = pr["sources"] or ["(none)"]
        probes[tag]["decoy"] += pr["cost"] * sum(x not in relevant for x in srcs) / len(srcs)
    rounds = []
    for b in sorted({d["batch"] for d in decs} | {r["batch"] for r in reports if r["batch"]}):
        new_sigs = sorted({matches.get(d["proposal_id"]) for d in promoted
                           if d["batch"] == b and matches.get(d["proposal_id"]) in planted})
        stops = await db["gate_results"].count_documents(
            {"customer": customer, "batch": b, "gate": "summary", "passed": False})
        rej = sum(d["batch"] == b and d["action"] == "reject" for d in decs)
        main = probes.get(f"{b}:main", {"units": 0.0, "decoy": 0.0})
        rounds.append({
            "round": b, "alerts_reviewed": 30 * b, "signals_learned": new_sigs,
            "probe_units": main["units"], "decoy_units": round(main["decoy"], 1),
            "units_per_signal": round(main["units"] / len(new_sigs), 1) if new_sigs else None,
            "fde_accepts": sum(d["batch"] == b and d["action"] == "accept" for d in decs),
            "fde_edits": sum(d["batch"] == b and d["action"] == "edit" for d in decs),
            "fde_rejects": rej, "stopped_by_gates": stops - rej,
        })
    ablation = [{"round": int(k.split(":")[0]), **v} for k, v in probes.items()
                if k.endswith(":ablation_no_priors")]
    base_report = reports[0].get("report_acc") if reports else None
    return {
        "rounds": rounds, "ablation": ablation, "static_base_acc": base_report,
        "strong_baseline": strong,
        "planted_signals": planted, "signals_learned": found,
        "signal_recall": len(found) / len(planted) if planted else 0,
        "holdout_by_batch": [{"batch": r["batch"], "acc": r.get("report_acc")}
                             for r in reports if r.get("report_acc") is not None],
        "noise_cases": reports[0].get("noise_cases") if reports else None,
        "proposals": n_props, "promoted": len(promoted), "survived": len(survived),
        "stopped_or_rejected": gate_fail,
        "fde_actions": dict(Counter(d["action"] for d in decs)),
        "fde_reasons": dict(Counter(d["reason_tag"] for d in decs)),
        "edit_distance_by_batch": {str(b): round(sum(x) / len(x), 3)
                                   for b, x in sorted(edits.items())},
        "decoy_spend": await _decoy_spend(customer),
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


async def comparison(customer: str) -> dict[str, Any]:
    doc = await app_db()["comparisons"].find_one({"_id": customer})
    return _clean(doc) if doc else {"rows": []}


async def probes(customer: str) -> list[dict[str, Any]]:
    """Every investigator probe in order, grouped client-side by round and run."""
    out = []
    async for pr in app_db()["probes"].find({"customer": customer}).sort("_id", 1):
        pr = _clean(pr)
        out.append({"round": pr["batch"], "run": pr["run_tag"], "tool": pr["tool"],
                    "args": pr["args"], "sources": pr["sources"], "cost": pr["cost"],
                    "preview": pr["preview"]})
    return out


async def ladder(customer: str) -> list[dict[str, Any]]:
    return [_clean(r) async for r in eval_db()["ladder"].find({"customer": customer})]
