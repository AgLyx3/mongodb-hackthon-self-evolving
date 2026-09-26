"""Batch loop for one customer (RESEARCH.md §5.4): run -> reveal -> investigate ->
propose -> gates/backtest -> simulated FDE -> promote -> usefulness.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from harness.adapters.llm.openrouter import BudgetExceeded, spent_usd
from harness.adapters.mongo.client import app_db, eval_db
from harness.adapters.mongo.store import load_units, reset_customer_run, save_version, set_live
from harness.config import get_settings
from harness.core.base_harness import base_units
from harness.core.conditions import Clause, Condition
from harness.core.fde import KeySignal, decide, judge_unit
from harness.core.kernel import KernelError, Proposal, promote
from harness.core.units import HarnessVersion, Unit, make_version
from harness.evolution.evaluate import CaseResult, glossary, load_cases, run_eval
from harness.evolution.gates import backtest, static_checks
from harness.evolution.investigator import investigate
from harness.evolution.proposer import propose

log = logging.getLogger(__name__)
PROBE_BUDGET = 24


async def answer_key(customer: str) -> tuple[list[KeySignal], list[dict[str, Any]]]:
    key = []
    async for s in eval_db()["answer_key"].find({"customer": customer}):
        cond = (Condition(all_of=tuple(Clause(**c) for c in s["condition"]["all_of"]))
                if s.get("condition") else None)
        key.append(KeySignal(signal_id=s["signal_id"], kind=s["kind"], condition=cond,
                             disposition=s.get("disposition"), field=s.get("field"),
                             meaning_keywords=tuple(s.get("meaning_keywords") or ()),
                             description=s["description"]))
    recs = [d["record"] async for d in app_db()["cases"].find({"customer": customer},
                                                               {"record": 1})]
    return key, recs


async def measure_noise(customer: str, units: list[Unit], holdout: list[dict[str, Any]],
                        model: str, k: int = 3) -> tuple[int, list[float]]:
    runs = [await run_eval(customer, units, holdout, model=model, rep=r, tag="noise")
            for r in range(k)]
    preds = [{x.case_id: x.predicted for x in run} for run in runs]
    flips = max(sum(a[c] != b[c] for c in a) for i, a in enumerate(preds)
                for b in preds[i + 1:])
    accs = [sum(x.correct for x in run) / len(run) for run in runs]
    return flips, accs


async def reveal(customer: str, batch: int) -> None:
    cases = [d async for d in eval_db()["case_labels"].find(
        {"customer": customer, "split": f"batch{batch}"})]
    await app_db()["outcomes"].insert_many([
        {"customer": customer, "case_id": c["_id"], "label": c["label"],
         "source": "batch_review", "batch": batch} for c in cases])


async def live_units_hashes(customer: str, model: str) -> set[str]:
    ptr = await app_db()["live_pointers"].find_one({"_id": f"{customer}|{model}"})
    if ptr is None:
        return set()
    v = await app_db()["harness_versions"].find_one({"_id": ptr["version"]})
    return set(v["unit_hashes"]) if v else set()


async def usefulness(customer: str, model: str) -> dict[str, float]:
    """Derived view (decision 3): credit sources behind promoted units that are still live.

    Only sources the investigator actually probed in that batch count (not the
    proposer's free-text claims), weighted by how little the FDE had to edit.
    """
    db = app_db()
    live = await live_units_hashes(customer, model)
    scores: Counter[str] = Counter()
    async for d in db["fde_decisions"].find({"customer": customer, "promoted": True}):
        if d.get("promoted_unit_hash") not in live:
            continue
        p = await db["proposals"].find_one({"_id": d["proposal_id"]})
        probed = {s async for pr in db["probes"].find(
            {"customer": customer, "batch": d["batch"], "run_tag": "main"})
            for s in pr["sources"]}
        weight = 1.0 - float(d.get("edit_distance", 0.0))
        for s in set((p or {}).get("evidence_refs", [])) & probed:
            scores[s] += round(weight, 3)
    return dict(scores)


def _fmt_scope(u: Unit | None) -> str | None:
    if u is None:
        return None
    return u.applies_when.render() if u.applies_when else f"definition of {u.field}"


async def score_report(customer: str, units: list[Unit], version: str, model: str,
                       batch: int, report: list[dict[str, Any]]) -> float:
    """Measure a version on the report split. Never used for any decision."""
    res = await run_eval(customer, units, report, model=model, tag="report")
    acc = sum(r.correct for r in res) / len(res)
    await eval_db()["report_scores"].insert_one({
        "customer": customer, "version": version, "model": model, "batch": batch, "acc": acc,
        "failed_calls": sum(r.predicted is None for r in res), "at": datetime.now(UTC)})
    return acc


async def run_customer(customer: str, batches: int = 3, *, use_priors: bool = True,
                       ablation_batch: int | None = 3) -> dict[str, Any]:
    s = get_settings()
    model = s.runtime_model
    ev = eval_db()
    await reset_customer_run(customer)
    for coll in ("report_scores", "batch_reports", "gate_private", "fde_matches"):
        await ev[coll].delete_many({"customer": customer})
    gl = await glossary(customer)
    key, all_records = await answer_key(customer)
    holdout = await load_cases(customer, ["holdout"])
    report = await load_cases(customer, ["report"])

    units = base_units()
    version = make_version(customer, units, None, "base")
    await save_version(customer, units, version)
    await set_live(customer, model, version.version_hash, reason="base harness", batch=0)
    noise_cases, noise_accs = await measure_noise(customer, units, holdout, model)
    rep_acc = await score_report(customer, units, version.version_hash, model, 0, report)
    await ev["batch_reports"].insert_one({
        "customer": customer, "batch": 0, "version": version.version_hash,
        "holdout_acc": noise_accs[0], "report_acc": rep_acc, "noise_cases": noise_cases,
        "noise_accs": noise_accs, "at": datetime.now(UTC)})
    log.info("%s noise band %d cases, accs %s; report %.0f%%", customer, noise_cases,
             noise_accs, 100 * rep_acc)

    revealed: list[int] = []
    for t in range(1, batches + 1):
        batch_cases = await load_cases(customer, [f"batch{t}"])
        await run_eval(customer, units, batch_cases, model=model, tag=f"work:b{t}")
        await reveal(customer, t)
        revealed.append(t)
        replay = await load_cases(customer, [f"batch{b}" for b in revealed])
        inc = await run_eval(customer, units, replay + holdout, model=model, tag=f"incumbent:b{t}")
        incumbent = {r.case_id: r for r in inc}
        labels_rec = {c["_id"]: c["record"] for c in replay}
        failures = [{"case_id": r.case_id, "predicted": r.predicted, "label": r.label,
                     "applied": r.applied, "record": labels_rec[r.case_id]}
                    for r in inc if r.case_id in labels_rec and not r.correct]
        priors = (await usefulness(customer, model)) if (use_priors and t > 1) else None
        findings, tb = await investigate(
            customer=customer, batch=t, units=units, failures=failures,
            revealed_batches=revealed, budget=PROBE_BUDGET, priors=priors, run_tag="main")
        await app_db()["findings"].insert_many([
            {"customer": customer, "batch": t, "run_tag": "main", **f.model_dump()}
            for f in findings] or [{"customer": customer, "batch": t, "empty": True}])

        if ablation_batch == t:
            await _ablation(customer, t, units, failures, revealed)

        proposals, _recalled = await propose(
            customer=customer, batch=t, parent_version=version.version_hash, live=units,
            findings=findings)
        promoted_ids: list[str] = []
        for p in proposals:
            if p.parent_version != version.version_hash:
                # An earlier proposal in this batch was promoted. Record the rebase
                # explicitly so the audit trail matches harness_versions.parent.
                await app_db()["gate_results"].insert_one({
                    "customer": customer, "batch": t, "proposal_id": p.proposal_id,
                    "gate": "rebase", "passed": True,
                    "detail": f"rebased from {p.parent_version} to {version.version_hash}",
                    "at": datetime.now(UTC)})
                p = p.model_copy(update={"parent_version": version.version_hash})
            units, version, promoted, incumbent = await _review(
                p, units, version, customer=customer, gl=gl, key=key, records=all_records,
                replay=replay, holdout=holdout, incumbent=incumbent, noise=noise_cases,
                model=model, batch=t)
            if promoted:
                promoted_ids.append(p.proposal_id)
                await score_report(customer, units, version.version_hash, model, t, report)

        hold_now = [incumbent[c["_id"]] for c in holdout]
        last = await ev["report_scores"].find_one({"customer": customer},
                                                  sort=[("at", -1)])
        await ev["batch_reports"].insert_one({
            "customer": customer, "batch": t, "version": version.version_hash,
            "holdout_acc": sum(r.correct for r in hold_now) / len(hold_now),
            "report_acc": last["acc"] if last else None,
            "failures_seen": len(failures), "probes_spent": tb.spent,
            "findings": len(findings), "proposals": len(proposals),
            "promoted": promoted_ids, "priors_used": priors or {},
            "usefulness_after": await usefulness(customer, model),
            "spent_usd": await spent_usd(), "at": datetime.now(UTC)})
        log.info("%s batch %d done: version %s, report %.0f%%", customer, t,
                 version.version_hash, 100 * (last["acc"] if last else 0))
    return {"customer": customer, "final_version": version.version_hash}


def _public_detail(rep_failed: str | None, passed: bool, fixed: int, broken: int) -> str:
    """Gate detail readable by the proposer: no holdout numbers (rules §5)."""
    if passed:
        return f"passed backtest; replay fixed {fixed}, broken {broken}"
    reasons = {"significance": "not enough gain on unseen cases",
               "activation": "the change never altered a decision where it applies",
               "replay": f"breaks {broken} previously-correct replay cases",
               "validity": "invalid change"}
    return f"{rep_failed}: {reasons.get(rep_failed or '', rep_failed)}"


async def _review(
    p: Proposal, units: list[Unit], version: HarnessVersion, *, customer: str,
    gl: dict[str, str], key: list[KeySignal], records: list[dict[str, Any]],
    replay: list[dict[str, Any]], holdout: list[dict[str, Any]],
    incumbent: dict[str, CaseResult], noise: int, model: str, batch: int,
) -> tuple[list[Unit], HarnessVersion, bool, dict[str, CaseResult]]:
    db, ev = app_db(), eval_db()

    async def gate(name: str, passed: bool, public: str, private: dict[str, Any] | None = None,
                   replay_ids: tuple[list[str], list[str]] | None = None) -> None:
        base = {"customer": customer, "batch": batch, "proposal_id": p.proposal_id,
                "gate": name, "passed": passed, "at": datetime.now(UTC)}
        pub = {**base, "detail": public}
        if replay_ids is not None:
            pub.update({"replay_fixed": replay_ids[0], "replay_broken": replay_ids[1]})
        await db["gate_results"].insert_one(pub)
        if private:
            await ev["gate_private"].insert_one({**base, **private})

    reason = static_checks(p, units, gl)
    if reason:
        await gate("static", False, reason)
        await gate("summary", False, reason)
        return units, version, False, incumbent
    await gate("static", True, "valid, lint clean")

    rep = await backtest(p, units, p.change.add, customer=customer, replay_cases=replay,
                         holdout_cases=holdout, incumbent=incumbent, noise_cases=noise,
                         model=model)
    priv = {"detail": rep.detail, "holdout_net": rep.holdout_net,
            "activations": rep.activations, "holdout_acc": rep.holdout_acc,
            "incumbent_holdout_acc": rep.incumbent_holdout_acc}
    await gate("backtest", rep.passed, _public_detail(rep.failed_gate, rep.passed,
               len(rep.replay_fixed), len(rep.replay_broken)), priv,
               (rep.replay_fixed, rep.replay_broken))
    # Answer-key match is recorded (privately) for metrics only.
    matched = judge_unit(p.change.add, key, records).signal_id if p.change.add else None
    await ev["fde_matches"].insert_one({"customer": customer, "batch": batch,
                                        "proposal_id": p.proposal_id, "signal": matched,
                                        "stage": "gates"})
    if not rep.passed:
        await gate("summary", False, _public_detail(rep.failed_gate, False,
                   len(rep.replay_fixed), len(rep.replay_broken)))
        return units, version, False, incumbent

    decision, sig = decide(p, units, key, records)
    await ev["fde_matches"].update_one({"proposal_id": p.proposal_id},
                                       {"$set": {"signal": sig, "stage": "fde"}})
    final_unit = decision.final_unit if decision.action == "edit" else p.change.add
    doc = {"customer": customer, "batch": batch, **decision.model_dump(mode="json"),
           "final_scope": _fmt_scope(final_unit), "promoted": False, "at": datetime.now(UTC)}
    if decision.action == "edit":
        # The FDE-edited unit goes through the same validity/lint and backtest (decision 7).
        edited = p.model_copy(update={"change": p.change.model_copy(
            update={"add": decision.final_unit})})
        reason = static_checks(edited, units, gl)
        if reason:
            await gate("static_fde_edit", False, reason)
            rep.passed = False
        else:
            rep = await backtest(p, units, decision.final_unit, customer=customer,
                                 replay_cases=replay, holdout_cases=holdout,
                                 incumbent=incumbent, noise_cases=noise, model=model)
            await gate("backtest_fde_edit", rep.passed, _public_detail(
                rep.failed_gate, rep.passed, len(rep.replay_fixed), len(rep.replay_broken)),
                {"detail": rep.detail, "holdout_net": rep.holdout_net,
                 "holdout_acc": rep.holdout_acc}, (rep.replay_fixed, rep.replay_broken))
    if decision.action in ("accept", "edit") and rep.passed:
        try:
            new_units, new_version = promote(p, decision, units, version)
        except KernelError as e:
            doc["promote_error"] = str(e)
            await db["fde_decisions"].insert_one(doc)
            await gate("summary", False, f"promotion refused: {e}")
            return units, version, False, incumbent
        await save_version(customer, new_units, new_version)
        await set_live(customer, model, new_version.version_hash, reason=decision.action,
                       proposal_id=p.proposal_id, batch=batch, edge=new_version.edge)
        added = next((u for u in new_units if u.content_hash not in
                      {x.content_hash for x in units}), None)
        doc.update({"promoted": True, "version": new_version.version_hash,
                    "promoted_unit_hash": added.content_hash if added else None,
                    "promoted_unit_id": added.unit_id if added else None,
                    "retired_unit_hash": p.change.retire_hash})
        await db["fde_decisions"].insert_one(doc)
        await gate("summary", True, f"promoted after FDE {decision.action}; "
                   f"replay fixed {len(rep.replay_fixed)}, broken {len(rep.replay_broken)}",
                   {"detail": rep.detail})
        new_inc = {r.case_id: r for r in rep.candidate_results}
        return new_units, new_version, True, new_inc
    await db["fde_decisions"].insert_one(doc)
    await gate("summary", False, f"FDE {decision.action} ({decision.reason_tag})")
    return units, version, False, incumbent


async def _ablation(customer: str, batch: int, units: list[Unit],
                    failures: list[dict[str, Any]], revealed: list[int]) -> None:
    """Same investigation without learned priors, for the 'learned where to look' metric."""
    try:
        findings, _tb = await investigate(
            customer=customer, batch=batch, units=units, failures=failures,
            revealed_batches=revealed, budget=PROBE_BUDGET, priors=None,
            run_tag="ablation_no_priors")
        await app_db()["findings"].insert_many([
            {"customer": customer, "batch": batch, "run_tag": "ablation_no_priors",
             **f.model_dump()} for f in findings] or [{"customer": customer, "batch": batch,
                                                        "run_tag": "ablation_no_priors",
                                                        "empty": True}])
    except BudgetExceeded:
        log.warning("ablation skipped: budget")


async def current_units(customer: str, model: str | None = None) -> list[Unit]:
    model = model or get_settings().runtime_model
    ptr = await app_db()["live_pointers"].find_one({"_id": f"{customer}|{model}"})
    assert ptr is not None, f"no live version for {customer}|{model}"
    return await load_units(ptr["version"])


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    asyncio.run(run_customer(sys.argv[1] if len(sys.argv) > 1 else "bank"))
