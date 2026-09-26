"""Gates before the FDE sees anything (rules §4), plus the pre-rollout backtest (decision 7).

validity -> lint -> backtest (replay of revealed batches + holdout) -> activation ->
significance vs the noise band -> no regression beyond noise on replay.
The proposer never sees holdout labels; only pass/fail and fixed/broken ids on
replay cases are shown to the FDE.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from harness.core.conditions import holds
from harness.core.kernel import KernelError, Proposal, validate_proposal
from harness.core.units import NoOpChange, Unit, apply_change
from harness.evolution.evaluate import CaseResult, run_eval

CASE_ID = re.compile(r"\b(NB-A\d+|zw_tx_\d+)\b")
OVERRIDE = re.compile(r"\b(ignore|override|bypass|disregard)\b.{0,40}\b(guardrail|kyc|due.diligence|"
                      r"harness|instruction|rule)s?\b", re.IGNORECASE)
KYC_FIELDS = ("kyc", "due_diligence")


@dataclass
class GateReport:
    passed: bool
    failed_gate: str | None
    detail: str
    candidate_units: list[Unit] = field(default_factory=list)
    holdout_acc: float | None = None
    incumbent_holdout_acc: float | None = None
    holdout_net: int = 0
    replay_fixed: list[str] = field(default_factory=list)
    replay_broken: list[str] = field(default_factory=list)
    activations: int = 0
    candidate_results: list[CaseResult] = field(default_factory=list)


def static_checks(p: Proposal, live: list[Unit], glossary: dict[str, str]) -> str | None:
    """Validity + lint. Returns a failure reason or None."""
    try:
        validate_proposal(p, live)
    except KernelError as e:
        return f"validity: {e}"
    u = p.change.add
    if u is not None:
        if u.kind == "rule":
            if u.applies_when is None or not u.applies_when.all_of or u.disposition is None:
                return "validity: rule needs clauses and a disposition"
            unknown = [c.path for c in u.applies_when.all_of if c.path not in glossary]
            if unknown:
                return f"validity: unknown fields {unknown}"
        if u.kind == "definition" and (u.field is None or u.field not in glossary):
            return f"validity: definition field {u.field!r} not in the record schema"
        if CASE_ID.search(f"{u.title} {u.text}"):
            return "lint: unit text hard-codes a case id"
        if OVERRIDE.search(f"{u.title} {u.text}"):
            return "lint: unit text tries to override guardrails or instructions"
        if (u.kind == "rule" and u.applies_when is not None and u.disposition != "request_info"
                and any(k in c.path for c in u.applies_when.all_of for k in KYC_FIELDS)):
            return "lint: a rule on KYC status may not change the KYC guardrail outcome"
    try:
        apply_change(live, u, p.change.retire_hash)
    except NoOpChange:
        return "validity: no-op change"
    if u is not None:
        live_ids = {x.unit_id: x for x in live}
        if u.unit_id in live_ids and live_ids[u.unit_id].content_hash != p.change.retire_hash:
            return f"validity: unit id {u.unit_id} is already live; supersede it instead"
    return None


def _index(results: list[CaseResult]) -> dict[str, CaseResult]:
    return {r.case_id: r for r in results}


async def backtest(
    p: Proposal, live: list[Unit], candidate_add: Unit | None, *, customer: str,
    replay_cases: list[dict[str, Any]], holdout_cases: list[dict[str, Any]],
    incumbent: dict[str, CaseResult], noise_cases: int, model: str,
) -> GateReport:
    try:
        cand_units = apply_change(live, candidate_add, p.change.retire_hash)
    except NoOpChange:
        return GateReport(False, "validity", "no-op change")
    res = await run_eval(customer, cand_units, replay_cases + holdout_cases, model=model,
                         tag=f"backtest:{p.proposal_id}")
    by = _index(res)
    hold_ids = [c["_id"] for c in holdout_cases]
    rep_ids = [c["_id"] for c in replay_cases]

    def ok(i: str) -> bool:
        # Infra/format failures on either side are excluded, never blamed on the harness.
        return by[i].predicted is not None and incumbent[i].predicted is not None

    def delta(ids: list[str]) -> tuple[list[str], list[str]]:
        fixed = [i for i in ids if ok(i) and by[i].correct and not incumbent[i].correct]
        broken = [i for i in ids if ok(i) and not by[i].correct and incumbent[i].correct]
        return fixed, broken

    h_fixed, h_broken = delta(hold_ids)
    r_fixed, r_broken = delta(rep_ids)
    # Activation is computed by the kernel, not taken from the model's self-report:
    # a rule fires on a case when its condition holds there AND the decision changed.
    records = {c["_id"]: c["record"] for c in replay_cases + holdout_cases}
    changed = [i for i in hold_ids + rep_ids if ok(i) and by[i].predicted != incumbent[i].predicted]
    if candidate_add is not None and candidate_add.applies_when is not None:
        activations = sum(holds(records[i], candidate_add.applies_when) for i in changed)
    else:
        activations = len(changed)
    rep = GateReport(
        passed=False, failed_gate=None, detail="", candidate_units=cand_units,
        holdout_acc=sum(by[i].correct for i in hold_ids) / len(hold_ids),
        incumbent_holdout_acc=sum(incumbent[i].correct for i in hold_ids) / len(hold_ids),
        holdout_net=len(h_fixed) - len(h_broken), replay_fixed=r_fixed,
        replay_broken=r_broken, activations=activations, candidate_results=res)
    threshold = max(2, noise_cases + 1)
    if candidate_add is not None and activations == 0:
        rep.failed_gate = "activation"
        rep.detail = "the change never altered a decision where it applies"
    elif rep.holdout_net < threshold:
        rep.failed_gate = "significance"
        rep.detail = (f"holdout net {rep.holdout_net:+d} cases, needs >= +{threshold} "
                      f"(noise band {noise_cases} cases)")
    elif len(r_broken) > noise_cases:
        rep.failed_gate = "replay"
        rep.detail = f"breaks {len(r_broken)} previously-correct replay cases"
    else:
        rep.passed = True
        rep.detail = (f"holdout {rep.incumbent_holdout_acc:.0%} -> {rep.holdout_acc:.0%} "
                      f"(net {rep.holdout_net:+d}); replay fixed {len(r_fixed)}, "
                      f"broken {len(r_broken)}; fired {activations}x")
    if not rep.passed and not rep.detail:
        rep.detail = rep.failed_gate or ""
    return rep
