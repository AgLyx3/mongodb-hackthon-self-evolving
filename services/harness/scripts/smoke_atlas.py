"""Connectivity + permission smoke test against Atlas (manual, not part of pytest).

Checks: both users can connect and read; the proposer user can insert into
`proposals` but is refused on any other collection.
"""

import asyncio

from pymongo.errors import OperationFailure

from harness.adapters.mongo.client import app_db, proposer_db


async def main() -> None:
    app, prop = app_db(), proposer_db()
    print("app ping:", (await app.command("ping"))["ok"])
    print("proposer ping:", (await prop.command("ping"))["ok"])

    await app["_smoke"].insert_one({"k": "app-write"})
    print("app write _smoke: ok")

    r = await prop["proposals"].insert_one({"_smoke": True})
    print("proposer insert proposals: ok")
    await app["proposals"].delete_one({"_id": r.inserted_id})

    for coll in ("harness_versions", "live_pointers", "_smoke"):
        try:
            await prop[coll].insert_one({"_smoke": True})
            print(f"FAIL: proposer could write {coll}")
        except OperationFailure as e:
            print(f"proposer write {coll}: refused (code {e.code})")
    try:
        await prop["proposals"].update_one({}, {"$set": {"x": 1}})
        print("FAIL: proposer could update proposals")
    except OperationFailure as e:
        print(f"proposer update proposals: refused (code {e.code})")

    print("proposer read _smoke:", await prop["_smoke"].count_documents({}) >= 1)
    await app["_smoke"].drop()


if __name__ == "__main__":
    asyncio.run(main())
