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


async def usefulness(customer: str) -> dict[str, float]:
    """Derived view (decision 3): credit sources behind promoted units still live."""
    db = app_db()
    ptr = await db["live_pointers"].find_one({"customer": customer})
    live = set((await db["harness_versions"].find_one({"_id": ptr["version"]}))["unit_hashes"])
    scores: Counter[str] = Counter()
    async for d in db["fde_decisions"].find({"customer": customer, "promoted": True}):
        if d.get("promoted_unit_hash") in live:
            p = await db["proposals"].find_one({"_id": d["proposal_id"]})
            for s in (p or {}).get("evidence_refs", []):
                scores[s] += 1.0
    return dict(scores)


def _fmt_scope(u: Unit | None) -> str | None:
    if u is None:
        return None
    return u.applies_when.render() if u.applies_when else f"definition of {u.field}"


async def run_customer(customer: str, batches: int = 3, *, use_priors: bool = True,
                       ablation_batch: int | None = 3) -> dict[str, Any]:
    s = get_settings()
    model = s.runtime_model
    db = app_db()
    await reset_customer_run(customer)
    gl = await glossary(customer)
    key, all_records = await answer_key(customer)
    holdout = await load_cases(customer, ["holdout"])

    units = base_units()
    version = make_version(customer, units, None, "base")
    await save_version(customer, units, version)
    await set_live(customer, model, version.version_hash, reason="base harness", batch=0)
    noise_cases, noise_accs = await measure_noise(customer, units, holdout, model)
    await db["batch_reports"].insert_one({
        "customer": customer, "batch": 0, "version": version.version_hash,
        "holdout_acc": noise_accs[0], "noise_cases": noise_cases, "noise_accs": noise_accs,
        "at": datetime.now(UTC)})
    log.info("%s noise band %d cases, accs %s", customer, noise_cases, noise_accs)

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
        priors = (await usefulness(customer)) if (use_priors and t > 1) else None
        findings, tb = await investigate(
            customer=customer, batch=t, units=units, failures=failures,
            revealed_batches=revealed, budget=PROBE_BUDGET, priors=priors, run_tag="main")
        await db["findings"].insert_many([
            {"customer": customer, "batch": t, "run_tag": "main", **f.model_dump()}
            for f in findings] or [{"customer": customer, "batch": t, "empty": True}])

        if ablation_batch == t:
            await _ablation(customer, t, units, failures, revealed)

        proposals, recalled = await propose(
            customer=customer, batch=t, parent_version=version.version_hash, live=units,
            findings=findings)
        promoted_ids: list[str] = []
        for p in proposals:
            p = p.model_copy(update={"parent_version": version.version_hash})  # rebase
            units, version, promoted, incumbent = await _review(
                p, units, version, customer=customer, gl=gl, key=key, records=all_records,
                replay=replay, holdout=holdout, incumbent=incumbent, noise=noise_cases,
                model=model, batch=t)
            if promoted:
                promoted_ids.append(p.proposal_id)

        hold_now = [incumbent[c["_id"]] for c in holdout]
        await db["batch_reports"].insert_one({
            "customer": customer, "batch": t, "version": version.version_hash,
            "holdout_acc": sum(r.correct for r in hold_now) / len(hold_now),
            "failures_seen": len(failures), "probes_spent": tb.spent,
            "findings": len(findings), "proposals": len(proposals),
            "promoted": promoted_ids, "priors_used": priors or {},
            "usefulness_after": await usefulness(customer),
            "spent_usd": await spent_usd(), "at": datetime.now(UTC)})
        log.info("%s batch %d done: version %s, holdout %.0f%%", customer, t,
                 version.version_hash, 100 * sum(r.correct for r in hold_now) / len(hold_now))
    return {"customer": customer, "final_version": version.version_hash}


async def _review(
    p: Proposal, units: list[Unit], version: HarnessVersion, *, customer: str,
    gl: dict[str, str], key: list[KeySignal], records: list[dict[str, Any]],
    replay: list[dict[str, Any]], holdout: list[dict[str, Any]],
    incumbent: dict[str, CaseResult], noise: int, model: str, batch: int,
) -> tuple[list[Unit], HarnessVersion, bool, dict[str, CaseResult]]:
    db = app_db()

    async def gate(name: str, passed: bool, detail: str, extra: dict[str, Any] | None = None
                   ) -> None:
        await db["gate_results"].insert_one({
            "customer": customer, "batch": batch, "proposal_id": p.proposal_id, "gate": name,
            "passed": passed, "detail": detail, **(extra or {}), "at": datetime.now(UTC)})

    reason = static_checks(p, units, gl)
    if reason:
        await gate("static", False, reason)
        await gate("summary", False, reason)
        return units, version, False, incumbent
    await gate("static", True, "valid, lint clean")

    rep = await backtest(p, units, p.change.add, customer=customer, replay_cases=replay,
                         holdout_cases=holdout, incumbent=incumbent, noise_cases=noise,
                         model=model)
    extra = {"replay_fixed": rep.replay_fixed, "replay_broken": rep.replay_broken,
             "holdout_net": rep.holdout_net, "activations": rep.activations,
             "holdout_acc": rep.holdout_acc, "incumbent_holdout_acc": rep.incumbent_holdout_acc}
    await gate("backtest", rep.passed, rep.detail, extra)
    # Answer-key match is recorded for metrics only; the FDE never sees gate-failed ones.
    matched = judge_unit(p.change.add, key, records).signal_id if p.change.add else None
    if not rep.passed:
        await gate("summary", False, f"{rep.failed_gate}: {rep.detail}",
                   {"matched_signal": matched})
        return units, version, False, incumbent

    decision, sig = decide(p, units, key, records)
    final_unit = decision.final_unit if decision.action == "edit" else p.change.add
    doc = {"customer": customer, "batch": batch, **decision.model_dump(mode="json"),
           "matched_signal": sig, "final_scope": _fmt_scope(final_unit),
           "promoted": False, "at": datetime.now(UTC)}
    if decision.action == "edit":
        # Decision 7: the FDE-edited unit is backtested too before rollout.
        rep = await backtest(p, units, decision.final_unit, customer=customer,
                             replay_cases=replay, holdout_cases=holdout, incumbent=incumbent,
                             noise_cases=noise, model=model)
        await gate("backtest_fde_edit", rep.passed, rep.detail, {
            "replay_fixed": rep.replay_fixed, "replay_broken": rep.replay_broken,
            "holdout_net": rep.holdout_net, "holdout_acc": rep.holdout_acc})
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
                       proposal_id=p.proposal_id, batch=batch)
        added = next((u for u in new_units if u.content_hash not in
                      {x.content_hash for x in units}), None)
        doc.update({"promoted": True, "version": new_version.version_hash,
                    "promoted_unit_hash": added.content_hash if added else None,
                    "promoted_unit_id": added.unit_id if added else None})
        await db["fde_decisions"].insert_one(doc)
        await gate("summary", True, f"promoted after FDE {decision.action}: {rep.detail}",
                   {"matched_signal": sig})
        new_inc = {r.case_id: r for r in rep.candidate_results}
        return new_units, new_version, True, new_inc
    await db["fde_decisions"].insert_one(doc)
    await gate("summary", False, f"FDE {decision.action} ({decision.reason_tag})",
               {"matched_signal": sig})
    return units, version, False, incumbent


async def _ablation(customer: str, batch: int, units: list[Unit],
                    failures: list[dict[str, Any]], revealed: list[int]) -> None:
    """Same investigation without learned priors, for the 'learned where to look' metric."""
    try:
        findings, tb = await investigate(
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


async def current_units(customer: str) -> list[Unit]:
    ptr = await app_db()["live_pointers"].find_one({"customer": customer})
    return await load_units(ptr["version"])


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    asyncio.run(run_customer(sys.argv[1] if len(sys.argv) > 1 else "bank"))
