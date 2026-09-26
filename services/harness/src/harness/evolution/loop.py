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
from harness.adapters.mongo.store import finish_run, load_units, save_version, set_live, start_run
from harness.config import get_settings
from harness.core.base_harness import base_units
from harness.core.conditions import Clause, Condition
from harness.core.fde import KeySignal, decide, judge_unit
from harness.core.fde_retro import FailedCase, render_feedback, render_playbook
from harness.core.kernel import FdeDecision, KernelError, Proposal, promote, unit_edit_distance
from harness.core.units import HarnessVersion, Unit, make_version
from harness.evolution.evaluate import CaseResult, glossary, load_cases, run_eval
from harness.evolution.gates import backtest, static_checks
from harness.evolution.investigator import investigate
from harness.datagen.registry import module_for
from harness.evolution.proposer import propose, revise
from harness.evolution.retro import active_lessons, run_retro, update_playbook

log = logging.getLogger(__name__)
PROBE_BUDGET = 24


def canary(signal_id: str) -> str:
    import hashlib

    return "KEY-" + hashlib.sha256(signal_id.encode()).hexdigest()[:8]


async def answer_key(customer: str) -> tuple[list[KeySignal], list[dict[str, Any]]]:
    """Answer key for the simulated FDE. Each description carries a canary token so
    any leak of answer-key text into FDE output or the harness is detectable."""
    key = []
    async for s in eval_db()["answer_key"].find({"customer": customer}):
        cond = (Condition(all_of=tuple(Clause(**c) for c in s["condition"]["all_of"]))
                if s.get("condition") else None)
        key.append(KeySignal(signal_id=s["signal_id"], kind=s["kind"], condition=cond,
                             disposition=s.get("disposition"), field=s.get("field"),
                             meaning_keywords=tuple(s.get("meaning_keywords") or ()),
                             description=f"{s['description']} [{canary(s['signal_id'])}]",
                             locations=tuple(s.get("locations") or ())))
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
                       ablation_batch: int | None = 3, fde_mode: str = "retro",
                       fde_noise: float = 0.0, fde_seed: int = 0) -> dict[str, Any]:
    s = get_settings()
    fde = {"mode": fde_mode, "noise": fde_noise, "seed": fde_seed,
           "rubric": getattr(module_for(customer), "presentation_rubric", None)}
    model = s.runtime_model
    ev = eval_db()
    run_id = await start_run(customer, {"fde_mode": fde_mode, "fde_noise": fde_noise,
                                        "fde_seed": fde_seed, "runtime_model": model})
    fde["run_id"] = run_id
    log.info("%s run %s started", customer, run_id)
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
    retro_on = fde_mode == "retro"
    retro_ctx = {"feedback": "(no feedback yet)", "playbook": "(no lessons yet)",
                 "targets": "(none)"}
    replay: list[dict[str, Any]] = []
    for t in range(1, batches + 1):
        batch_cases = await load_cases(customer, [f"batch{t}"])
        work = await run_eval(customer, units, batch_cases, model=model, tag=f"work:b{t}")
        await reveal(customer, t)
        revealed.append(t)
        replay = await load_cases(customer, [f"batch{b}" for b in revealed])
        retro_doc = None
        if retro_on and t >= 2:
            # Results-driven retrospective: round-t failures under the harness live then,
            # traced back through the agent's own trail (method feedback, not rule review).
            recs = {c["_id"]: c["record"] for c in batch_cases}
            retro_doc = await _retro(customer, run_id, t, "start", work, recs, units, key,
                                     all_records, {c["_id"] for c in replay})
            retro_ctx = await _retro_context(customer, run_id, retro_doc)
        inc = await run_eval(customer, units, replay + holdout, model=model, tag=f"incumbent:b{t}")
        incumbent = {r.case_id: r for r in inc}
        labels_rec = {c["_id"]: c["record"] for c in replay}
        failures = [{"case_id": r.case_id, "predicted": r.predicted, "label": r.label,
                     "applied": r.applied, "record": labels_rec[r.case_id]}
                    for r in inc if r.case_id in labels_rec and not r.correct]
        priors = (await usefulness(customer, model)) if (use_priors and t > 1) else None
        findings, tb = await investigate(
            customer=customer, batch=t, units=units, failures=failures,
            revealed_batches=revealed, budget=PROBE_BUDGET, priors=priors, run_tag="main",
            feedback=retro_ctx["feedback"], playbook=retro_ctx["playbook"])
        await app_db()["findings"].insert_many([
            {"customer": customer, "batch": t, "run_tag": "main", **f.model_dump()}
            for f in findings] or [{"customer": customer, "batch": t, "empty": True}])

        if ablation_batch == t:
            await _ablation(customer, t, units, failures, revealed, retro_ctx)

        labels_by_id = {r.case_id: r.label for r in inc}
        visible = [(c["_id"], c["record"], labels_by_id[c["_id"]]) for c in replay]
        proposals, _recalled = await propose(
            customer=customer, batch=t, parent_version=version.version_hash, live=units,
            findings=findings, targets=retro_ctx["targets"], playbook=retro_ctx["playbook"])
        if ablation_batch == t:
            await _uptake_ablation(customer, t, version, units, findings, proposals, key,
                                   all_records, visible, fde, retro_ctx)
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
                model=model, batch=t, fde=fde, visible=visible)
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
            "retro_causes": _cause_counts(retro_doc),
            "spent_usd": await spent_usd(), "at": datetime.now(UTC)})
        log.info("%s batch %d done: version %s, report %.0f%%", customer, t,
                 version.version_hash, 100 * (last["acc"] if last else 0))
    if retro_on and replay:
        # Final retrospective: revealed cases the final harness still gets wrong (for metrics).
        recs = {c["_id"]: c["record"] for c in replay}
        final = [incumbent[cid] for cid in recs if cid in incumbent]
        doc = await _retro(customer, run_id, batches + 1, "final", final, recs, units, key,
                           all_records, set(recs))
        await ev["batch_reports"].update_one(
            {"customer": customer, "batch": batches},
            {"$set": {"retro_causes_final": _cause_counts(doc)}})
    await _ladder_summary(customer, fde, version.version_hash)
    await finish_run(run_id, version.version_hash)
    return {"customer": customer, "final_version": version.version_hash}


async def _retro(customer: str, run_id: str, batch: int, phase: str,
                 results: list[CaseResult], records: dict[str, dict[str, Any]],
                 units: list[Unit], key: list[KeySignal], all_records: list[dict[str, Any]],
                 revealed_ids: set[str]) -> dict[str, Any]:
    failed = [FailedCase(case_id=r.case_id, record=records[r.case_id], predicted=r.predicted,
                         label=r.label, applied=tuple(r.applied), case_type=r.case_type)
              for r in results if not r.correct and r.predicted is not None
              and r.case_id in records]  # an infra failure (no answer) is not a method miss
    doc = await run_retro(customer=customer, run_id=run_id, batch=batch, phase=phase,
                          failed=failed, units=units, key=key, records=all_records,
                          revealed_case_ids=revealed_ids)
    await _leak_check_text(customer, batch, f"retro:{phase}",
                           " ".join(i["message"] for i in doc["items"]))
    try:
        await update_playbook(customer=customer, run_id=run_id, batch=batch)
    except BudgetExceeded:
        log.warning("lesson writing skipped: budget")
    log.info("%s retro %s round %d: %s", customer, phase, batch,
             [(i["cause"], i["n_cases"]) for i in doc["items"]])
    return doc


async def _retro_context(customer: str, run_id: str, doc: dict[str, Any]) -> dict[str, str]:
    items = doc["items"]
    targets = [i for i in items if i["suggested_action"] in ("revise_unit", "retire_unit")]
    tgt = "\n".join(f"- {i['target_unit_id']}: {i['suggested_action']} ({i['cause']}). "
                     f"{i['message']}" for i in targets) or "(none)"
    return {"feedback": render_feedback(items),
            "playbook": render_playbook(await active_lessons(customer, run_id)),
            "targets": tgt}


def _cause_counts(doc: dict[str, Any] | None) -> dict[str, int]:
    """Failed cases explained per retro cause (empty when no retro ran)."""
    out: Counter[str] = Counter()
    for i in (doc or {}).get("items", []):
        out[i["cause"]] += int(i.get("n_cases", len(i["cases"])))
    return dict(out)


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
    fde: dict[str, Any], visible: list[tuple[str, dict[str, Any], str]],
    attempt: int = 0, prev_unit: Unit | None = None,
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
        fixable = ("unknown fields" in reason or "not in the record schema" in reason)
        if fixable and attempt == 0 and p.change.add is not None:
            # A correctable mistake (misnamed field): give the valid field list and one
            # retry, like the FDE's hint path. Nothing about the answer is revealed.
            feedback = (f"Automated validity check: {reason}. Valid record fields are: "
                        f"{', '.join(sorted(gl))}.")
            p2 = await revise(original=p, feedback=feedback, counterexamples=[], live=units,
                              parent_version=version.version_hash)
            if p2 is not None:
                await gate("revision", True, f"revised after validity feedback as {p2.proposal_id}")
                return await _review(p2, units, version, customer=customer, gl=gl, key=key,
                                     records=records, replay=replay, holdout=holdout,
                                     incumbent=incumbent, noise=noise, model=model,
                                     batch=batch, fde=fde, visible=visible, attempt=1,
                                     prev_unit=p.change.add)
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

    if fde["mode"] == "none":
        # Ladder baseline: no reviewer; anything that passes the gates goes live.
        decision = FdeDecision(proposal_id=p.proposal_id, fde_id="auto:no-fde",
                               action="accept", reason_tag="correct",
                               rationale="Auto-accepted: passed all gates (no-FDE baseline).")
        sig = matched
    elif fde["mode"] == "retro":
        # The FDE reviews results and method after each round, not each proposal. The
        # gates still screen every change and promotion still goes through the kernel.
        decision = FdeDecision(proposal_id=p.proposal_id, fde_id="auto:gates",
                               action="accept", reason_tag="correct",
                               rationale="Auto-accepted: passed all gates (retro mode; the "
                                         "FDE reviews round results, not single proposals).")
        sig = matched
    else:
        decision, sig = decide(p, units, key, records, fde["rubric"], mode=fde["mode"],
                               visible=visible, allow_revise=attempt == 0,
                               noise=fde["noise"], seed=fde["seed"])
    await _leak_check(customer, batch, p.proposal_id, decision)
    await ev["fde_matches"].update_one({"proposal_id": p.proposal_id},
                                       {"$set": {"signal": sig, "stage": "fde"}})
    final_unit = decision.final_unit if decision.action == "edit" else p.change.add
    doc = {"customer": customer, "batch": batch, **decision.model_dump(mode="json"),
           "final_scope": _fmt_scope(final_unit), "promoted": False, "attempt": attempt,
           "fde_mode": fde["mode"], "at": datetime.now(UTC)}
    if prev_unit is not None:
        # How far the agent's own revision moved (hint-only feedback, no FDE edit).
        doc["revision_distance"] = unit_edit_distance(prev_unit, p.change.add)
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
    if decision.action == "revise" and p.change.add is not None:
        by_id = {cid: (rec, lab) for cid, rec, lab in visible}
        ce = [{"case_id": c, "record": by_id[c][0], "label": by_id[c][1]}
              for c in decision.counterexamples if c in by_id]
        p2 = await revise(original=p, feedback=decision.rationale, counterexamples=ce,
                          live=units, parent_version=version.version_hash)
        if p2 is None:
            await gate("revision", False, "proposer could not produce a revision")
            return units, version, False, incumbent
        await gate("revision", True, f"revised by the proposer as {p2.proposal_id}")
        return await _review(p2, units, version, customer=customer, gl=gl, key=key,
                             records=records, replay=replay, holdout=holdout,
                             incumbent=incumbent, noise=noise, model=model, batch=batch,
                             fde=fde, visible=visible, attempt=1, prev_unit=p.change.add)
    return units, version, False, incumbent


async def _leak_check_text(customer: str, batch: int, ref: str, text: str) -> None:
    """Flag any answer-key canary token in FDE retrospective text."""
    await eval_db()["leak_checks"].insert_one({
        "customer": customer, "batch": batch, "proposal_id": ref, "leaked": "KEY-" in text,
        "fde_id": "sim-fde:jordan", "at": datetime.now(UTC)})


async def _leak_check(customer: str, batch: int, proposal_id: str, d: FdeDecision) -> None:
    """Flag any answer-key text (canary token) in what the FDE sends back."""
    text = d.rationale + (d.final_unit.text if d.final_unit else "")
    await eval_db()["leak_checks"].insert_one({
        "customer": customer, "batch": batch, "proposal_id": proposal_id,
        "leaked": "KEY-" in text, "fde_id": d.fde_id, "at": datetime.now(UTC)})


async def _uptake_ablation(customer: str, batch: int, version: HarnessVersion,
                           units: list[Unit], findings: list[Any], main: list[Proposal],
                           key: list[KeySignal], records: list[dict[str, Any]],
                           visible: list[tuple[str, dict[str, Any], str]],
                           fde: dict[str, Any], retro_ctx: dict[str, str]) -> None:
    """Feedback uptake: first-pass FDE verdicts on the same findings with memory of past
    FDE decisions (recall) vs without. Nothing from the no-recall arm is promoted."""
    try:
        norecall, _ = await propose(customer=customer, batch=batch,
                                    parent_version=version.version_hash, live=units,
                                    findings=findings, recall_enabled=False, persist=False,
                                    targets=retro_ctx["targets"], playbook=retro_ctx["playbook"])
    except BudgetExceeded:
        return
    rows = []
    for arm, props in (("recall", main), ("norecall", norecall)):
        for p in props:
            d, sig = decide(p, units, key, records, fde["rubric"], mode="hints",
                            visible=visible, allow_revise=True)
            rows.append({"customer": customer, "batch": batch, "arm": arm,
                         "proposal_id": p.proposal_id, "signal": sig, "action": d.action,
                         "reason": d.reason_tag, "at": datetime.now(UTC)})
    if rows:
        await eval_db()["uptake"].insert_many(rows)


async def _ladder_summary(customer: str, fde: dict[str, Any], final_version: str) -> None:
    ev, db = eval_db(), app_db()
    reports = [r async for r in ev["batch_reports"].find({"customer": customer}).sort("batch", 1)]
    decs = [d async for d in db["fde_decisions"].find({"customer": customer})]
    leaks = await ev["leak_checks"].count_documents({"customer": customer, "leaked": True})
    checks = await ev["leak_checks"].count_documents({"customer": customer})
    await ev["ladder"].replace_one(
        {"_id": f"{customer}|{fde['mode']}|{fde['noise']}"},
        {"_id": f"{customer}|{fde['mode']}|{fde['noise']}", "customer": customer,
         "mode": fde["mode"], "noise": fde["noise"], "seed": fde["seed"],
         "run_id": fde.get("run_id"), "final_version": final_version,
         "report_by_round": [r.get("report_acc") for r in reports],
         "fde_actions": dict(Counter(d["action"] for d in decs)),
         "promoted": sum(bool(d.get("promoted")) for d in decs),
         "leaks": leaks, "leak_checks": checks, "at": datetime.now(UTC)}, upsert=True)


async def _ablation(customer: str, batch: int, units: list[Unit],
                    failures: list[dict[str, Any]], revealed: list[int],
                    retro_ctx: dict[str, str]) -> None:
    """Same investigation without learned priors, for the 'learned where to look' metric."""
    try:
        findings, _tb = await investigate(
            customer=customer, batch=batch, units=units, failures=failures,
            revealed_batches=revealed, budget=PROBE_BUDGET, priors=None,
            run_tag="ablation_no_priors", feedback=retro_ctx["feedback"],
            playbook=retro_ctx["playbook"])
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
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("customer", nargs="?", default="bank")
    ap.add_argument("--fde-mode", default="retro", choices=["retro", "hints", "oracle", "none"])
    ap.add_argument("--fde-noise", type=float, default=0.0)
    ap.add_argument("--fde-seed", type=int, default=0)
    a = ap.parse_args()
    asyncio.run(run_customer(a.customer, fde_mode=a.fde_mode, fde_noise=a.fde_noise,
                             fde_seed=a.fde_seed))
