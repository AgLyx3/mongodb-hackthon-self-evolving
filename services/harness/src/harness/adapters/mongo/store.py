"""Version store: immutable units + versions, one live pointer per (customer, model).

Only the kernel (app credentials) calls these. `set_live()` is called only from
promotion after an FDE decision; every pointer move is also appended to
`pointer_events` so history is never lost.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from harness.adapters.mongo.client import app_db
from harness.core.units import HarnessVersion, Unit


def _now() -> datetime:
    return datetime.now(UTC)


async def save_version(customer: str, units: list[Unit], version: HarnessVersion) -> None:
    db = app_db()
    for u in units:
        await db["units"].update_one(
            {"_id": u.content_hash},
            {"$setOnInsert": {"customer": customer, "unit": u.model_dump(mode="json"),
                              "created_at": _now()}}, upsert=True)
    await db["harness_versions"].update_one(
        {"_id": version.version_hash},
        {"$setOnInsert": {**version.model_dump(mode="json"), "created_at": _now()}},
        upsert=True)


async def load_units(version_hash: str) -> list[Unit]:
    db = app_db()
    v = await db["harness_versions"].find_one({"_id": version_hash})
    if v is None:
        raise KeyError(version_hash)
    docs = {d["_id"]: d async for d in db["units"].find({"_id": {"$in": v["unit_hashes"]}})}
    return [Unit.model_validate(docs[h]["unit"]) for h in v["unit_hashes"]]


async def load_version(version_hash: str) -> HarnessVersion:
    v = await app_db()["harness_versions"].find_one({"_id": version_hash})
    if v is None:
        raise KeyError(version_hash)
    return HarnessVersion.model_validate(v)


async def live_version(customer: str, model: str) -> str | None:
    doc = await app_db()["live_pointers"].find_one({"_id": f"{customer}|{model}"})
    return doc["version"] if doc else None


async def set_live(customer: str, model: str, version_hash: str, *, reason: str,
                   proposal_id: str | None = None, batch: int = 0,
                   edge: str = "base") -> None:
    db = app_db()
    prev = await live_version(customer, model)
    await db["live_pointers"].update_one(
        {"_id": f"{customer}|{model}"},
        {"$set": {"version": version_hash, "customer": customer, "model": model,
                  "updated_at": _now()}}, upsert=True)
    await db["pointer_events"].insert_one({
        "customer": customer, "model": model, "from": prev, "to": version_hash,
        # The edge lives on the (append-only) event, not the version: content can
        # recur (a retire can recreate an earlier hash) and must not lose lineage.
        "edge": edge, "reason": reason, "proposal_id": proposal_id, "batch": batch,
        "at": _now()})


async def revert(customer: str, model: str, to_version: str, *, reason: str,
                 batch: int = 0) -> None:
    """FDE revert: point the live pointer at an earlier version of this customer."""
    from harness.core.kernel import check_revert

    check_revert(customer, await load_version(to_version))
    await set_live(customer, model, to_version, reason=f"fde_revert: {reason}", batch=batch,
                   edge="reverts")


async def reset_customer_run(customer: str) -> None:
    """Clear evolution state for a fresh run (keeps data, cache, and spend ledger)."""
    db = app_db()
    q: dict[str, Any] = {"customer": customer}
    for coll in ("proposals", "gate_results", "fde_decisions", "probes", "findings",
                 "pointer_events", "batch_reports", "source_usefulness"):
        await db[coll].delete_many(q)
    await db["outcomes"].delete_many({"customer": customer, "batch": {"$gt": 0}})
    await db["traces"].delete_many({"customer": customer, "tag": {"$ne": "calibration"}})
    await db["live_pointers"].delete_many(q)
