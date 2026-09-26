"""Run the triage agent over a set of cases under one harness version; store traces.

Scoring reads labels from fde_eval (kernel side). Callers on the proposer side
only ever receive aggregates or revealed-batch outcomes, never holdout labels.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from harness.adapters.llm.openrouter import LlmFailure
from harness.adapters.mongo.client import app_db, eval_db
from harness.adapters.runtime.triage import triage
from harness.core.units import Unit, make_version


@dataclass
class CaseResult:
    case_id: str
    predicted: str | None
    label: str
    correct: bool
    applied: list[str]
    cost: float
    case_type: str


async def load_cases(customer: str, splits: list[str]) -> list[dict[str, Any]]:
    cur = app_db()["cases"].find({"customer": customer, "split": {"$in": splits}})
    return [d async for d in cur]


async def glossary(customer: str) -> dict[str, str]:
    doc = await app_db()["customers"].find_one({"_id": customer})
    assert doc is not None
    return dict(doc["record_schema"])


async def run_eval(
    customer: str, units: list[Unit], cases: list[dict[str, Any]], *, model: str,
    rep: int = 0, tag: str = "",
) -> list[CaseResult]:
    labels = {d["_id"]: d async for d in eval_db()["case_labels"].find(
        {"_id": {"$in": [c["_id"] for c in cases]}})}
    gl = await glossary(customer)
    version = make_version(customer, units, None, "base").version_hash

    async def one(c: dict[str, Any]) -> CaseResult:
        lab = labels[c["_id"]]
        try:
            res, cost, _hit = await triage(units, c["record"], gl, model=model, rep=rep)
            pred, applied = res.disposition, res.applied_unit_ids
        except LlmFailure:
            pred, applied, cost = None, [], 0.0
        return CaseResult(case_id=c["_id"], predicted=pred, label=lab["label"],
                          correct=pred == lab["label"], applied=applied, cost=cost,
                          case_type=lab["case_type"])

    results = await asyncio.gather(*(one(c) for c in cases))
    if results:
        await app_db()["traces"].insert_many([
            {"customer": customer, "version": version, "model": model, "rep": rep, "tag": tag,
             "case_id": r.case_id, "predicted": r.predicted, "correct": r.correct,
             "applied": r.applied, "cost": r.cost} for r in results])
    return list(results)


def accuracy(results: list[CaseResult]) -> float:
    return sum(r.correct for r in results) / len(results) if results else 0.0


def by_type(results: list[CaseResult]) -> dict[str, tuple[int, int]]:
    out: dict[str, list[int]] = {}
    for r in results:
        out.setdefault(r.case_type, [0, 0])
        out[r.case_type][0] += r.correct
        out[r.case_type][1] += 1
    return {k: (v[0], v[1]) for k, v in sorted(out.items())}
