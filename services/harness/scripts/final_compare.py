"""Final comparison on the report split (decision 8), stored for the UI.

The report split is never used for any decision, so these numbers are unbiased.

Rows: {mid, strong} x {base harness, evolved harness (live version)}.
The strong-model + evolved row is a first, small look at cross-model transfer
(the harness was evolved on the mid-tier model's trajectories).
"""

import asyncio
import sys
from datetime import UTC, datetime

from harness.adapters.llm.openrouter import spent_usd
from harness.adapters.mongo.client import app_db
from harness.config import get_settings
from harness.core.base_harness import base_units
from harness.evolution.evaluate import accuracy, by_type, load_cases, run_eval
from harness.evolution.loop import current_units


async def main(customer: str) -> None:
    s = get_settings()
    holdout = await load_cases(customer, ["report"])
    evolved = await current_units(customer)
    rows = []
    for harness_name, units in (("base", base_units()), ("evolved", evolved)):
        for role, model in (("mid", s.runtime_model), ("strong", s.strong_model)):
            res = await run_eval(customer, units, holdout, model=model, tag="final_compare")
            failed = sum(r.predicted is None for r in res)
            sig = [r for r in res if not r.case_type.startswith("base.")]
            rows.append({"harness": harness_name, "role": role, "model": model,
                         "acc": accuracy(res), "signal_acc": accuracy(sig),
                         "failed_calls": failed, "by_type": by_type(res)})
            print(f"{customer} {harness_name:8s} {role:6s} {model:32s} acc {accuracy(res):.0%} "
                  f"signal {accuracy(sig):.0%} failed {failed}")
    await app_db()["comparisons"].replace_one(
        {"_id": customer}, {"_id": customer, "rows": rows, "at": datetime.now(UTC)}, upsert=True)
    print(f"spent so far: ${await spent_usd():.3f}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "bank"))
