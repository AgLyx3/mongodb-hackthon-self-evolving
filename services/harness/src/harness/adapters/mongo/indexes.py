"""Index declarations, created idempotently. Vector index uses Atlas Automated
Embedding (autoEmbed, voyage-4): Atlas embeds `text` itself, queries pass text.
Changing the model means rebuilding the index (plan it as a migration)."""

from __future__ import annotations

import asyncio

from pymongo import ASCENDING
from pymongo.errors import OperationFailure
from pymongo.operations import SearchIndexModel

from harness.adapters.mongo.client import app_db
from harness.config import get_settings

EVIDENCE_INDEX = "evidence_autoembed"
PROPOSALS_INDEX = "proposals_autoembed"


async def ensure_indexes() -> None:
    db = app_db()
    await db["cases"].create_index([("customer", ASCENDING), ("split", ASCENDING)])
    await db["outcomes"].create_index([("customer", ASCENDING), ("case_id", ASCENDING)])
    await db["traces"].create_index([("customer", ASCENDING), ("version", ASCENDING),
                                     ("model", ASCENDING), ("case_id", ASCENDING)])
    await db["proposals"].create_index([("customer", ASCENDING), ("batch", ASCENDING)])
    await db["fde_decisions"].create_index("proposal_id")
    await db["gate_results"].create_index("proposal_id")
    await db["probes"].create_index([("customer", ASCENDING), ("batch", ASCENDING)])
    await db["units"].create_index("customer")
    await db["harness_versions"].create_index("customer")

    model = get_settings().embedding_model
    await _ensure_search_index(db["evidence"], EVIDENCE_INDEX, {
        "fields": [
            {"type": "autoEmbed", "modality": "text", "path": "text", "model": model},
            {"type": "filter", "path": "customer"},
            {"type": "filter", "path": "source_id"},
            {"type": "filter", "path": "kind"},
        ]})
    await _ensure_search_index(db["proposals"], PROPOSALS_INDEX, {
        "fields": [
            {"type": "autoEmbed", "modality": "text", "path": "summary", "model": model},
            {"type": "filter", "path": "customer"},
        ]})


async def _ensure_search_index(coll, name: str, definition: dict) -> None:  # type: ignore[no-untyped-def]
    if coll.name not in await coll.database.list_collection_names():
        await coll.database.create_collection(coll.name)
    existing = [ix async for ix in await coll.list_search_indexes()]
    if any(ix["name"] == name for ix in existing):
        return
    try:
        await coll.create_search_index(
            SearchIndexModel(definition=definition, name=name, type="vectorSearch"))
    except OperationFailure as e:
        if "already exists" not in str(e):
            raise


async def wait_queryable(coll_name: str, name: str, timeout_s: int = 600) -> bool:
    coll = app_db()[coll_name]
    for _ in range(timeout_s // 5):
        ixs = [ix async for ix in await coll.list_search_indexes(name)]
        if ixs and ixs[0].get("queryable"):
            return True
        await asyncio.sleep(5)
    return False
