"""Dataset audits for decisions 9 and 11. Pure functions over generated customers.

- `naive_base`: what an agent that follows the *base harness* literally would
  answer. Every planted signal must flip this on its cases, otherwise the
  signal teaches nothing.
- `difference_audit`: the two customers share no signal except shared.* and
  reuse no signal type.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from harness.core.conditions import Disposition
from harness.datagen.spec import Customer


def naive_base(customer: str, record: dict[str, Any]) -> Disposition:
    if customer not in ("bank", "fintech"):
        from harness.datagen.registry import module_for

        return module_for(customer).naive_base(record)  # type: ignore[no-any-return]
    if customer == "bank":
        t, a, al = record["txn"], record["account"], record["alert"]
        if a["kyc_status"] == "incomplete":
            return "request_info"
        if (t["amount_usd"] >= 10000 or t["cp_risk_rating"] == "high"
                or al["alert_type"] == "structuring"):
            return "escalate"
        return "close_false_positive"
    t, w = record["txn"], record["wallet"]
    if w["kyc_lvl"] == 0:
        return "request_info"
    # A literal reader takes "H" for high risk (the trap) and knows no crypto rule.
    if t["amt"] >= 10000 or t["cp_ctry_risk"] in ("H", "X"):
        return "escalate"
    return "close_false_positive"


def signal_flip_report(c: Customer) -> dict[str, tuple[int, int]]:
    """signal_id -> (cases of that type in eval splits, cases the naive base gets wrong)."""
    out: dict[str, tuple[int, int]] = {}
    for s in c.signals:
        cases = [x for x in c.cases if x.case_type == s.signal_id and x.split != "history"]
        wrong = sum(naive_base(c.customer, x.record) != x.label for x in cases)
        out[s.signal_id] = (len(cases), wrong)
    return out


def holdout_counts(c: Customer) -> Counter[str]:
    return Counter(x.case_type for x in c.cases if x.split == "holdout")


def difference_audit(a: Customer, b: Customer) -> list[str]:
    problems: list[str] = []
    ids_a = {s.signal_id for s in a.signals if not s.shared}
    ids_b = {s.signal_id for s in b.signals if not s.shared}
    if ids_a & ids_b:
        problems.append(f"shared non-shared signal ids: {ids_a & ids_b}")
    types_a = {s.signal_type for s in a.signals if not s.shared}
    types_b = {s.signal_type for s in b.signals if not s.shared}
    if types_a & types_b:
        problems.append(f"signal types reused: {types_a & types_b}")
    shared_a = {s.signal_id for s in a.signals if s.shared}
    shared_b = {s.signal_id for s in b.signals if s.shared}
    if shared_a != shared_b or len(shared_a) != 1:
        problems.append(f"expected exactly one common shared signal: {shared_a} vs {shared_b}")
    kinds_a = {e.kind for e in a.manifest}
    kinds_b = {e.kind for e in b.manifest}
    if kinds_a == kinds_b:
        problems.append("source mixes are identical")
    return problems
