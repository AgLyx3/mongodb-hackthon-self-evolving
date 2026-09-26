"""Run the triage agent over a set of cases under one harness version; store traces.

Scoring reads labels from fde_eval (kernel side). Callers on the proposer side
only ever receive aggregates or revealed-batch outcomes, never holdout labels.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from harness.adapters.llm.openrouter import LlmFailure
from harness.adapters.mongo.client import app_db, eval_db
from harness.adapters.runtime import triage as single_runtime
from harness.adapters.runtime.triage import TriageResult
from harness.config import get_settings
from harness.core.units import Unit, make_version

PRIVATE_SPLITS = ("holdout", "report")

TriageFn = Callable[..., Awaitable[tuple[TriageResult, float, bool]]]


def select_runtime(name: str | None = None) -> tuple[str, TriageFn]:
    """(runtime name, triage coroutine) for settings.triage_runtime or `name`."""
    name = name or get_settings().triage_runtime
    if name == "single":
        return name, single_runtime.triage
    if name == "deep":
        from harness.adapters.runtime import triage_deep  # heavy import, only when used

        return name, triage_deep.triage
    raise ValueError(f"unknown triage runtime {name!r}")


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
    runtime, triage = select_runtime()

    async def one(c: dict[str, Any]) -> CaseResult:
        lab = labels[c["_id"]]
        pred, applied, cost = None, [], 0.0
        for attempt in range(2):  # one retry: infra/format failures are not the harness
            try:
                res, cost, _hit = await triage(units, c["record"], gl, model=model, rep=rep,
                                               case_id=c["_id"], tag=tag, version=version)
                pred, applied = res.disposition, res.applied_unit_ids
                break
            except LlmFailure:
                continue
        return CaseResult(case_id=c["_id"], predicted=pred, label=lab["label"],
                          correct=pred == lab["label"], applied=applied, cost=cost,
                          case_type=lab["case_type"])

    results = await asyncio.gather(*(one(c) for c in cases))
    # Traces for holdout/report cases go to fde_eval: with `correct` (or even just the
    # prediction across reps) they would leak labels to anyone with the proposer's FIND.
    private = {c["_id"] for c in cases if c.get("split") in PRIVATE_SPLITS}
    docs = [{"customer": customer, "version": version, "model": model, "runtime": runtime,
             "rep": rep, "tag": tag,
             "case_id": r.case_id, "predicted": r.predicted, "correct": r.correct,
             "applied": r.applied, "cost": r.cost} for r in results]
    pub = [d for d in docs if d["case_id"] not in private]
    prv = [d for d in docs if d["case_id"] in private]
    if pub:
        await app_db()["traces"].insert_many(pub)
    if prv:
        await eval_db()["traces_private"].insert_many(prv)
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
