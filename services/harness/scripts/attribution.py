"""How much of the evolved harness's accuracy did the agent earn, vs the simulated FDE?

The simulated FDE edits too-broad/too-narrow rules to the exact answer-key scope,
which injects knowledge the agent never found. This scores the report split with:
  live         the promoted harness (FDE edits included)
  agent_only   FDE-edited units replaced by the proposer's original unit
  accepted     FDE-edited units removed (only units accepted as proposed)
  base         the generic base harness
Stored in `comparisons.attribution` for the UI.
"""

import asyncio
import sys
from datetime import UTC, datetime

from harness.adapters.llm.openrouter import spent_usd
from harness.adapters.mongo.client import app_db
from harness.config import get_settings
from harness.core.base_harness import base_units
from harness.core.units import Unit
from harness.evolution.evaluate import accuracy, by_type, load_cases, run_eval
from harness.evolution.loop import current_units


async def main(customer: str, model_role: str) -> None:
    s = get_settings()
    model = s.runtime_model if model_role == "mid" else s.strong_model
    db = app_db()
    live = await current_units(customer)
    edited: dict[str, Unit] = {}  # live content hash -> proposer's original unit
    async for d in db["fde_decisions"].find({"customer": customer, "promoted": True,
                                             "action": "edit"}):
        p = await db["proposals"].find_one({"_id": d["proposal_id"]})
        orig = ((p or {}).get("change") or {}).get("add")
        if orig and d.get("promoted_unit_hash"):
            edited[d["promoted_unit_hash"]] = Unit.model_validate(orig)
    agent_only = [edited.get(u.content_hash, u) for u in live]
    accepted = [u for u in live if u.content_hash not in edited]
    report = await load_cases(customer, ["report"])
    rows = []
    for name, units in (("live", live), ("agent_only", agent_only), ("accepted", accepted),
                        ("base", base_units())):
        res = await run_eval(customer, units, report, model=model, tag=f"attribution:{name}")
        sig = [r for r in res if not r.case_type.startswith("base.")]
        rows.append({"variant": name, "model": model, "acc": accuracy(res),
                     "signal_acc": accuracy(sig), "fde_edited_units": len(edited),
                     "by_type": by_type(res)})
        print(f"{customer} {model_role} {name:10s} acc {accuracy(res):.0%} "
              f"signal {accuracy(sig):.0%}")
    await db["comparisons"].update_one(
        {"_id": customer},
        {"$set": {f"attribution_{model_role}": rows, "attribution_at": datetime.now(UTC)}},
        upsert=True)
    print(f"spent so far: ${await spent_usd():.3f}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "bank",
                     sys.argv[2] if len(sys.argv) > 2 else "mid"))
