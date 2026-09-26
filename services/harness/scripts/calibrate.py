"""Decision 8 calibration: mid-tier and strong models on the base harness, holdout split.

If the strong model already solves the planted-signal cases, the dataset is too
easy and must be redesigned before building the loop.
"""

import asyncio
import sys

from harness.adapters.llm.openrouter import spent_usd
from harness.config import get_settings
from harness.core.base_harness import base_units
from harness.evolution.evaluate import accuracy, by_type, load_cases, run_eval


async def main(customers: list[str]) -> None:
    s = get_settings()
    for customer in customers:
        cases = await load_cases(customer, ["holdout"])
        for model in (s.runtime_model, s.strong_model):
            res = await run_eval(customer, base_units(), cases, model=model, tag="calibration")
            sig = [r for r in res if not r.case_type.startswith("base.")]
            print(f"\n{customer} | {model} | overall {accuracy(res):.0%} | "
                  f"base-type cases {accuracy([r for r in res if r.case_type.startswith('base.')]):.0%} | "
                  f"signal cases {accuracy(sig):.0%} | failed calls "
                  f"{sum(r.predicted is None for r in res)}")
            for t, (ok, n) in by_type(res).items():
                print(f"   {t:34s} {ok}/{n}")
    print(f"\nspent so far: ${await spent_usd():.3f}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or ["bank", "fintech"]))
