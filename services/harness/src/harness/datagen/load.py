"""Load generated customers into Atlas. Idempotent: drops and rewrites per customer.

fde_harness (readable by the proposer):
  customers, cases (records only), outcomes (labels the investigator may see:
  fintech history outcomes; later, revealed batch outcomes), qc_sheet (bank),
  evidence (text chunks, autoEmbed)
fde_eval (app user only):
  case_labels, answer_key, oracle
"""

from __future__ import annotations

import asyncio

from harness.adapters.mongo.client import app_db, eval_db
from harness.adapters.mongo.indexes import EVIDENCE_INDEX, ensure_indexes, wait_queryable
from harness.datagen.registry import module_for
from harness.datagen.spec import Customer


async def load_customer(c: Customer) -> None:
    db, ev = app_db(), eval_db()
    q = {"customer": c.customer}
    for coll in ("cases", "outcomes", "qc_sheet", "evidence"):
        await db[coll].delete_many(q)
    for coll in ("case_labels", "answer_key", "oracle"):
        await ev[coll].delete_many(q)
    await db["customers"].replace_one({"_id": c.customer}, {
        "_id": c.customer, "display_name": c.display_name, "industry": c.industry,
        "record_schema": c.record_schema,
        # The manifest as the customer described it; relevance is answer-key only.
        "manifest": [{"source_id": e.source_id, "kind": e.kind, "described_as": e.described_as}
                     for e in c.manifest],
    }, upsert=True)

    await db["cases"].insert_many([
        {"_id": x.case_id, "customer": c.customer, "split": x.split, "record": x.record}
        for x in c.cases])
    await ev["case_labels"].insert_many([
        {"_id": x.case_id, "customer": c.customer, "split": x.split, "label": x.label,
         "case_type": x.case_type} for x in c.cases])

    qc = [ch for ch in c.chunks if ch.source_id == "qc_sheet"]
    if not qc and c.history_labels:
        # No QC sheet: history labels are observed outcomes (quantitative, no comments).
        await db["outcomes"].insert_many([
            {"customer": c.customer, "case_id": cid, "label": lab, "source": "history_outcome",
             "batch": 0} for cid, lab in c.history_labels.items()])
    if qc:
        await db["qc_sheet"].insert_many([
            {"customer": c.customer, "case_id": ch.meta["case_id"],
             "analyst_disposition": ch.meta["analyst"], "qc_disposition": ch.meta["qc"],
             "score": ch.meta["score"], "comment": ch.text.split("Comment: ", 1)[1]}
            for ch in qc])
    await db["evidence"].insert_many([
        {"customer": c.customer, "source_id": ch.source_id, "kind": ch.kind, "text": ch.text,
         "avail_round": int(ch.meta.get("available_from_round", 0)), "meta": ch.meta}
        for ch in c.chunks])

    await ev["answer_key"].insert_many(
        [{"customer": c.customer, "aux": False, **s.model_dump(mode="json")} for s in c.signals]
        + [{"customer": c.customer, "aux": True, **s.model_dump(mode="json")}
           for s in c.aux_facts])
    await ev["oracle"].insert_many([
        {"customer": c.customer, "keyword": k,
         "answers": [{"from_round": 0, "answer": v}] if isinstance(v, str) else v}
        for k, v in c.oracle.items()])


async def main(names: list[str]) -> None:
    await ensure_indexes()
    for c in (module_for(n).build() for n in names):
        await load_customer(c)
        print(f"loaded {c.customer}: {len(c.cases)} cases, {len(c.chunks)} chunks")
    ok = await wait_queryable("evidence", EVIDENCE_INDEX)
    print("evidence vector index queryable:", ok)


if __name__ == "__main__":
    import sys

    asyncio.run(main(sys.argv[1:] or ["bank", "fintech"]))
