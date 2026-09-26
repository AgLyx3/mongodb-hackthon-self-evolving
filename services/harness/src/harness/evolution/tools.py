"""Investigator tools. Every call is a *probe*: logged with a cost and the
sources it touched, so we can measure where the investigator spends effort.

Visibility (decision 1, rules §5): the investigator sees records, evidence,
the QC sheet, history outcomes, and outcomes of batches already revealed.
It never sees holdout or unrevealed labels (those live in fde_eval).
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from harness.adapters.mongo.client import app_db, eval_db
from harness.adapters.mongo.indexes import EVIDENCE_INDEX
from harness.core.conditions import Clause, Condition, get_path, holds

COSTS = {"label_breakdown": 1, "field_stats": 1, "search_evidence": 1, "read_source": 2,
         "ask_customer": 3}
RECORD_SOURCE = {"bank": "case_records", "fintech": "txn_records"}

TOOL_SPECS: list[dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "label_breakdown",
        "description": "Quantitative. Among cases whose correct disposition is known (QC "
                       "reviews, historical outcomes, revealed batches), filter by clauses "
                       "and group by one field; returns counts of each correct disposition "
                       "per group. Use it to test whether a pattern predicts the outcome. "
                       "Cost 1.",
        "parameters": {"type": "object", "properties": {
            "clauses": {"type": "array", "description": "AND-ed filters", "items": {
                "type": "object", "properties": {
                    "path": {"type": "string", "description": "dotted field, e.g. txn.amt"},
                    "op": {"type": "string", "enum": ["==", "!=", ">=", "<=", ">", "<"]},
                    "value": {"type": "string", "description": "number, date or text"}},
                "required": ["path", "op", "value"]}},
            "group_by": {"type": "string", "description": "dotted field to group by"}},
            "required": ["clauses", "group_by"]}}},
    {"type": "function", "function": {
        "name": "field_stats",
        "description": "Quantitative. Distribution of one record field across all records "
                       "(top values, or min/median/max for numbers). Cost 1.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}},
                       "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "search_evidence",
        "description": "Qualitative. Semantic search over documents, interviews, chat, QC "
                       "comments and exports. Optionally restrict to one source_id. Returns "
                       "the 5 most relevant passages with their source. Cost 1.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"},
            "source_id": {"type": "string", "description": "optional; empty for all"}},
            "required": ["query", "source_id"]}}},
    {"type": "function", "function": {
        "name": "read_source",
        "description": "Read a source sequentially, 8 passages at a time. Cost 2.",
        "parameters": {"type": "object", "properties": {
            "source_id": {"type": "string"}, "offset": {"type": "integer"}},
            "required": ["source_id", "offset"]}}},
    {"type": "function", "function": {
        "name": "ask_customer",
        "description": "Ask the customer's contact one short, specific question (e.g. what a "
                       "field or code means). Expensive: cost 3. They answer only what they "
                       "know.",
        "parameters": {"type": "object", "properties": {"question": {"type": "string"}},
                       "required": ["question"]}}},
]


def parse_value(v: Any) -> Any:
    if not isinstance(v, str):
        return v
    s = v.strip()
    for cast in (int, float):
        try:
            return cast(s)
        except ValueError:
            pass
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    return s.strip("'\"")


class Toolbox:
    def __init__(self, customer: str, batch: int, run_tag: str, budget: int,
                 revealed_batches: list[int]) -> None:
        self.customer, self.batch, self.run_tag = customer, batch, run_tag
        self.budget, self.spent = budget, 0
        self.revealed = revealed_batches
        self._labeled: list[tuple[dict[str, Any], str]] | None = None
        self._records: list[dict[str, Any]] | None = None

    async def _all_records(self) -> list[dict[str, Any]]:
        if self._records is None:
            cur = app_db()["cases"].find(
                {"customer": self.customer,
                 "split": {"$in": ["history"] + [f"batch{b}" for b in self.revealed]}},
                {"record": 1})
            self._records = [d["record"] async for d in cur]
        return self._records

    async def _labeled_rows(self) -> list[tuple[dict[str, Any], str]]:
        if self._labeled is None:
            db = app_db()
            labels: dict[str, str] = {}
            async for o in db["outcomes"].find({"customer": self.customer,
                                                "batch": {"$in": [0] + self.revealed}}):
                labels[o["case_id"]] = o["label"]
            async for q in db["qc_sheet"].find({"customer": self.customer}):
                labels[q["case_id"]] = q["qc_disposition"]
            cur = db["cases"].find({"_id": {"$in": list(labels)}}, {"record": 1})
            self._labeled = [(d["record"], labels[d["_id"]]) async for d in cur]
        return self._labeled

    async def _log(self, tool: str, args: dict[str, Any], sources: list[str],
                   result_preview: str) -> None:
        await app_db()["probes"].insert_one({
            "customer": self.customer, "batch": self.batch, "run_tag": self.run_tag,
            "tool": tool, "args": args, "sources": sorted(set(sources)),
            "cost": COSTS[tool], "preview": result_preview[:300]})

    async def call(self, name: str, args: dict[str, Any]) -> str:
        if name not in COSTS:
            return json.dumps({"error": f"unknown tool {name}"})
        if self.spent + COSTS[name] > self.budget:
            return json.dumps({"error": "probe budget exhausted; write your findings now"})
        self.spent += COSTS[name]
        try:
            out, sources = await getattr(self, f"_t_{name}")(**args)
        except Exception as e:  # noqa: BLE001 - tools must never crash the loop
            out, sources = {"error": f"{type(e).__name__}: {e}"[:200]}, []
        text = json.dumps(out, default=str)[:3500]
        await self._log(name, args, sources, text)
        return text

    async def _t_label_breakdown(self, clauses: list[dict[str, Any]], group_by: str
                                 ) -> tuple[Any, list[str]]:
        cond = Condition(all_of=tuple(Clause(path=c["path"], op=c["op"],
                                             value=parse_value(c["value"])) for c in clauses))
        groups: dict[str, Counter[str]] = {}
        for rec, lab in await self._labeled_rows():
            if holds(rec, cond):
                key = str(get_path(rec, group_by))
                groups.setdefault(key, Counter())[lab] += 1
        top = sorted(groups.items(), key=lambda kv: -sum(kv[1].values()))[:15]
        src = "qc_sheet" if self.customer == "bank" else RECORD_SOURCE[self.customer]
        return ({"group_by": group_by, "groups": {k: dict(v) for k, v in top},
                 "n": sum(sum(v.values()) for v in groups.values())}, [src])

    async def _t_field_stats(self, path: str) -> tuple[Any, list[str]]:
        vals = [get_path(r, path) for r in await self._all_records()]
        vals = [v for v in vals if v is not None]
        if vals and all(isinstance(v, (int, float)) for v in vals):
            s = sorted(vals)
            out: Any = {"n": len(s), "min": s[0], "median": s[len(s) // 2], "max": s[-1],
                        "p90": s[int(len(s) * 0.9)]}
        else:
            out = {"n": len(vals), "top": Counter(map(str, vals)).most_common(12)}
        return out, [RECORD_SOURCE[self.customer]]

    async def _t_search_evidence(self, query: str, source_id: str = "") -> tuple[Any, list[str]]:
        flt: dict[str, Any] = {"customer": self.customer}
        if source_id:
            flt["source_id"] = source_id
        pipe = [{"$vectorSearch": {"index": EVIDENCE_INDEX, "path": "text", "query": query,
                                   "filter": flt, "numCandidates": 100, "limit": 5}},
                {"$project": {"_id": 1, "source_id": 1, "text": 1}}]
        hits = [d async for d in await app_db()["evidence"].aggregate(pipe)]
        return ([{"id": str(h["_id"]), "source_id": h["source_id"], "text": h["text"][:400]}
                 for h in hits], [h["source_id"] for h in hits])

    async def _t_read_source(self, source_id: str, offset: int = 0) -> tuple[Any, list[str]]:
        cur = app_db()["evidence"].find({"customer": self.customer, "source_id": source_id}
                                        ).skip(max(0, offset)).limit(8)
        rows = [{"id": str(d["_id"]), "text": d["text"][:400]} async for d in cur]
        return {"source_id": source_id, "offset": offset, "passages": rows}, [source_id]

    async def _t_ask_customer(self, question: str) -> tuple[Any, list[str]]:
        q = question.lower()
        async for o in eval_db()["oracle"].find({"customer": self.customer}):
            if o["keyword"].lower() in q:
                return {"answer": o["answer"]}, ["customer_contact"]
        return {"answer": "Sorry, I don't know."}, ["customer_contact"]
