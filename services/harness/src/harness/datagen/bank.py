"""Customer 1 (development): Northbridge Bank. Synthetic, fictional, labeled as such.

Signal homes: QC reviewer comments (cross-case patterns) + interviews.
Vocabulary: case/account, formal field names. Labels come from QC review.
"""

from __future__ import annotations

import random
from typing import Any

from harness.core.conditions import Clause, Condition, Disposition, holds
from harness.datagen.audit import naive_base
from harness.datagen.spec import Case, Chunk, Customer, Signal, SourceEntry

C = "bank"


def _c(*clauses: tuple[str, str, Any]) -> Condition:
    return Condition(all_of=tuple(Clause(path=p, op=o, value=v) for p, o, v in clauses))  # type: ignore[arg-type]


SIGNALS: list[Signal] = [
    Signal(
        signal_id="shared.dormant_reactivation", customer=C, shared=True, kind="rule",
        description="Dormant account (>=180 days) suddenly moving >= $5,000 is escalated.",
        condition=_c(("account.dormant_days", ">=", 180), ("txn.amount_usd", ">=", 5000)),
        disposition="escalate", locations=("interview_ops_lead", "qc_sheet"),
        signal_type="interview_remark",
    ),
    Signal(
        signal_id="bank.payroll_batches", customer=C, shared=False, kind="rule",
        description="Structuring alerts on corporate payroll batches (purpose PAYR) are closed.",
        condition=_c(("alert.alert_type", "==", "structuring"),
                     ("txn.purpose_code", "==", "PAYR"),
                     ("account.account_type", "==", "corporate")),
        disposition="close_false_positive", locations=("interview_senior_analyst",),
        signal_type="interview_tacit_exception",
    ),
    Signal(
        signal_id="bank.established_corridor", customer=C, shared=False, kind="rule",
        description="SOP scope error: high-risk-geo alerts on established relationships "
        "(>=24 months, >=3 prior payments on the corridor) are closed, not escalated.",
        condition=_c(("txn.cp_risk_rating", "==", "high"),
                     ("account.age_months", ">=", 24),
                     ("account.prior_corridor_count", ">=", 3)),
        disposition="close_false_positive", locations=("qc_sheet",),
        signal_type="sop_scope_error",
    ),
    Signal(
        signal_id="bank.rolling_30d", customer=C, shared=False, kind="rule",
        description="Definition mismatch: the $10k threshold means the rolling 30-day "
        "aggregate, so single payments under $10k with a 30-day total >= $10k escalate.",
        condition=_c(("txn.amount_usd", "<", 10000), ("txn.agg30_amt_usd", ">=", 10000)),
        disposition="escalate", locations=("qc_sheet", "interview_ops_lead"),
        signal_type="definition_mismatch",
    ),
    Signal(
        signal_id="bank.new_payee", customer=C, shared=False, kind="rule",
        description="QC convention: payments >= $3,000 to a payee added <= 7 days earlier "
        "get request_info.",
        condition=_c(("txn.payee_age_days", "<=", 7), ("txn.amount_usd", ">=", 3000)),
        disposition="request_info", locations=("qc_sheet",),
        signal_type="qc_only_convention",
    ),
]

_BY_ID = {s.signal_id: s for s in SIGNALS}
# Precedence of the true policy. First match wins.
_TRUTH_ORDER = [
    "base.kyc", "shared.dormant_reactivation", "bank.payroll_batches",
    "bank.established_corridor", "bank.rolling_30d", "bank.new_payee",
    "base.large", "base.high_risk", "base.structuring", "base.close",
]


def classify(record: dict[str, Any]) -> tuple[str, Disposition]:
    """Ground truth: which rule decides this case, and the correct disposition."""
    for rid in _TRUTH_ORDER:
        if rid == "base.kyc" and record["account"]["kyc_status"] == "incomplete":
            return rid, "request_info"
        if rid in _BY_ID:
            s = _BY_ID[rid]
            assert s.condition is not None and s.disposition is not None
            if holds(record, s.condition):
                return rid, s.disposition
        if rid == "base.large" and record["txn"]["amount_usd"] >= 10000:
            return rid, "escalate"
        if rid == "base.high_risk" and record["txn"]["cp_risk_rating"] == "high":
            return rid, "escalate"
        if rid == "base.structuring" and record["alert"]["alert_type"] == "structuring":
            return rid, "escalate"
    return "base.close", "close_false_positive"


# Target mix of case types for eval cases (each signal ~11-13% of cases).
MIX = {
    "base.kyc": 0.08, "base.large": 0.08, "base.high_risk": 0.07,
    "base.structuring": 0.06, "base.close": 0.14,
    "shared.dormant_reactivation": 0.11, "bank.payroll_batches": 0.11,
    "bank.established_corridor": 0.12, "bank.rolling_30d": 0.12, "bank.new_payee": 0.11,
}


def _sample(rng: random.Random, target: str, idx: int) -> dict[str, Any]:
    amount = round(rng.choice([rng.uniform(150, 2900), rng.uniform(3000, 9800)]), 2)
    rec: dict[str, Any] = {
        "alert": {
            "alert_id": f"NB-A{idx:05d}",
            "alert_type": rng.choice(["large_txn", "high_risk_geo", "rapid_movement",
                                      "structuring", "new_payee"]),
            "created_at": f"2026-{rng.randint(6, 9):02d}-{rng.randint(1, 28):02d}",
        },
        "txn": {
            "amount_usd": amount,
            "agg30_amt_usd": round(amount + rng.uniform(0, 4000), 2),
            "cp_risk_rating": rng.choice(["standard"] * 5 + ["high"]),
            "purpose_code": rng.choice(["GDS", "SVC", "FAM", "INV", "PAYR", "RENT"]),
            "payee_age_days": rng.randint(20, 900),
            "channel": rng.choice(["wire", "ach", "online"]),
        },
        "account": {
            "account_type": rng.choice(["retail", "retail", "corporate"]),
            "age_months": rng.randint(3, 120),
            "kyc_status": "complete",
            "dormant_days": rng.randint(0, 60),
            "prior_corridor_count": rng.randint(0, 2),
            "segment": rng.choice(["mass", "affluent", "smb"]),
        },
    }
    t, a, al = rec["txn"], rec["account"], rec["alert"]
    match target:
        case "base.kyc":
            a["kyc_status"] = "incomplete"
        case "base.large":
            t["amount_usd"] = round(rng.uniform(10000, 60000), 2)
            t["agg30_amt_usd"] = t["amount_usd"] + round(rng.uniform(0, 5000), 2)
            al["alert_type"] = "large_txn"
        case "base.high_risk":
            t["cp_risk_rating"], al["alert_type"] = "high", "high_risk_geo"
            a["age_months"] = rng.randint(3, 20)
        case "base.structuring":
            al["alert_type"] = "structuring"
            t["purpose_code"] = rng.choice(["GDS", "SVC", "INV"])
        case "shared.dormant_reactivation":
            a["dormant_days"] = rng.randint(180, 700)
            t["amount_usd"] = round(rng.uniform(5000, 9800), 2)
            t["agg30_amt_usd"] = t["amount_usd"]
            al["alert_type"] = "rapid_movement"
        case "bank.payroll_batches":
            al["alert_type"], t["purpose_code"] = "structuring", "PAYR"
            a["account_type"], a["segment"] = "corporate", "smb"
        case "bank.established_corridor":
            t["cp_risk_rating"], al["alert_type"] = "high", "high_risk_geo"
            a["age_months"] = rng.randint(24, 150)
            a["prior_corridor_count"] = rng.randint(3, 14)
        case "bank.rolling_30d":
            t["amount_usd"] = round(rng.uniform(2000, 9800), 2)
            t["agg30_amt_usd"] = round(rng.uniform(10000, 24000), 2)
        case "bank.new_payee":
            t["payee_age_days"] = rng.randint(0, 7)
            t["amount_usd"] = round(rng.uniform(3000, 9500), 2)
            al["alert_type"] = "new_payee"
    if target not in ("bank.rolling_30d", "base.large"):
        t["agg30_amt_usd"] = min(t["agg30_amt_usd"], 9900.0)
    return rec


def _gen(rng: random.Random, target: str, idx: int) -> dict[str, Any]:
    for _ in range(500):
        rec = _sample(rng, target, idx)
        rtype, label = classify(rec)
        if rtype != target:
            continue
        # A planted signal must flip what the base harness would say (decision 9).
        if not target.startswith("base.") and naive_base(C, rec) == label:
            continue
        return rec
    raise RuntimeError(f"could not sample {target}")


def _qc_comment(rng: random.Random, rtype: str, r: dict[str, Any]) -> str:
    t, a = r["txn"], r["account"]
    match rtype:
        case "bank.established_corridor":
            return rng.choice([
                f"Long-standing client ({a['age_months']} mo) and this corridor has "
                f"{a['prior_corridor_count']} prior payments. Geo flag alone doesn't justify "
                "an escalation here. Should have been closed.",
                f"Over-escalated. Relationship is {a['age_months']} months old with "
                f"{a['prior_corridor_count']} earlier payments to the same corridor; we close these.",
            ])
        case "bank.new_payee":
            return rng.choice([
                f"Payee was only added {t['payee_age_days']} day(s) before a "
                f"${t['amount_usd']:,.0f} payment. Team practice is to request info at that size.",
                f"Brand-new beneficiary ({t['payee_age_days']}d) and ${t['amount_usd']:,.0f}. "
                "Needed an RFI, not a close.",
            ])
        case "bank.rolling_30d":
            return rng.choice([
                f"Single payment is under 10k but the rolling 30-day total is "
                f"${t['agg30_amt_usd']:,.0f}. That's over the line. Escalate.",
                f"Analyst looked at the single amount only. 30-day aggregate "
                f"${t['agg30_amt_usd']:,.0f} crosses our threshold.",
            ])
        case "shared.dormant_reactivation":
            return (f"Account was quiet for {a['dormant_days']} days then ${t['amount_usd']:,.0f} "
                    "moved. Classic sleeper wake-up, should go up.")
        case "base.kyc":
            return "Correct, CDD file incomplete so RFI."
        case "base.large" | "base.high_risk" | "base.structuring":
            return rng.choice(["Correct escalation.", "Agree.", "Fine."])
        case _:
            return rng.choice(["Agree.", "OK.", "No issues.", "Fine, closed correctly."])


def _analyst_disposition(rtype: str, label: Disposition) -> Disposition:
    # Analysts follow the SOP literally, so they get the signal cases wrong,
    # except payroll batches, which senior analysts already close (tacit knowledge).
    sop = {
        "bank.established_corridor": "escalate",
        "bank.new_payee": "close_false_positive",
        "bank.rolling_30d": "close_false_positive",
        "shared.dormant_reactivation": "close_false_positive",
    }
    return sop.get(rtype, label)  # type: ignore[return-value]


def _allocate(rng: random.Random, n: int) -> list[str]:
    """Exactly n case types, proportional to MIX, shuffled."""
    types = [t for t, w in MIX.items() for _ in range(int(w * n))]
    while len(types) < n:
        types.append(rng.choices(list(MIX), weights=list(MIX.values()))[0])
    rng.shuffle(types)
    return types[:n]


def build(seed: int = 7) -> Customer:
    rng = random.Random(seed)
    cases: list[Case] = []
    idx = 0

    def make(target: str, split: str) -> Case:
        nonlocal idx
        idx += 1
        rec = _gen(rng, target, idx)
        rtype, label = classify(rec)
        return Case(case_id=rec["alert"]["alert_id"], customer=C, record=rec, label=label,
                    case_type=rtype, split=split)  # type: ignore[arg-type]

    # Eval cases: 3 batches x 30 + holdout 40, drawn from MIX.
    for split, n in (("batch1", 30), ("batch2", 30), ("batch3", 30), ("holdout", 40)):
        cases.extend(make(t, split) for t in _allocate(rng, n))

    # History: 200 past alerts (unlabeled records), 60 of them QC-reviewed.
    history = [make(t, "history") for t in rng.choices(list(MIX), weights=list(MIX.values()),
                                                         k=200)]
    cases.extend(history)
    qc_rows = rng.sample(history, 60)
    history_labels = {c.case_id: c.label for c in qc_rows}

    chunks: list[Chunk] = []
    for c in qc_rows:
        analyst = _analyst_disposition(c.case_type, c.label)
        score = 5 if analyst == c.label else rng.choice([2, 3])
        chunks.append(Chunk(
            source_id="qc_sheet", kind="qc_sheet",
            text=f"QC review of {c.case_id}: analyst={analyst}; qc={c.label}; score={score}/5. "
                 f"Comment: {_qc_comment(rng, c.case_type, c.record)}",
            meta={"case_id": c.case_id, "analyst": analyst, "qc": c.label, "score": score},
        ))
    chunks.extend(_texts())
    for i in range(40):
        chunks.append(Chunk(
            source_id="billing_export", kind="export",
            text=f"Invoice NB-INV-{3000 + i}: segment={rng.choice(['mass', 'affluent', 'smb'])}; "
                 f"monthly_fee=${rng.choice([0, 5, 12, 25])}; wire_fees=${rng.randint(0, 180)}; "
                 f"fx_markup_bps={rng.choice([0, 25, 50])}; statement_cycle="
                 f"{rng.choice(['EOM', 'MID'])}",
            meta={"row": i},
        ))

    # Report split: generated last so every earlier case is unchanged. It is never
    # used for any decision (gates select on holdout); it only measures versions.
    cases.extend(make(t, "report") for t in _allocate(rng, 40))

    return Customer(
        customer=C, display_name="Northbridge Bank (synthetic)", industry="retail & SMB bank",
        record_schema={
            "alert.alert_type": "alert category from the monitoring system",
            "alert.created_at": "alert creation date",
            "txn.amount_usd": "amount of the flagged payment",
            "txn.agg30_amt_usd": "sum of outgoing payments over the past 30 days",
            "txn.cp_risk_rating": "counterparty jurisdiction risk rating",
            "txn.purpose_code": "payment purpose code",
            "txn.payee_age_days": "days since the beneficiary was added",
            "txn.channel": "payment rail",
            "account.account_type": "retail or corporate",
            "account.age_months": "relationship length",
            "account.kyc_status": "customer due-diligence file status",
            "account.dormant_days": "days without activity before this payment",
            "account.prior_corridor_count": "earlier payments to the same country corridor",
            "account.segment": "customer segment",
        },
        manifest=[
            SourceEntry(source_id="case_records", kind="records", relevant=True,
                        described_as="All AML alerts with linked payment and account data."),
            SourceEntry(source_id="qc_sheet", kind="qc_sheet", relevant=True,
                        described_as="Monthly QC sample of closed alerts with reviewer notes."),
            SourceEntry(source_id="sop", kind="doc", relevant=True,
                        described_as="AML alert handling SOP v4.2, the official process."),
            SourceEntry(source_id="interview_ops_lead", kind="interview", relevant=True,
                        described_as="Onboarding interview with the AML operations lead."),
            SourceEntry(source_id="interview_senior_analyst", kind="interview", relevant=True,
                        described_as="Onboarding interview with a senior L1 analyst."),
            SourceEntry(source_id="interview_new_hire", kind="interview", relevant=False,
                        described_as="Onboarding interview with a recently hired analyst."),
            SourceEntry(source_id="billing_export", kind="export", relevant=False,
                        described_as="Account billing and fee export; might explain segments."),
        ],
        signals=SIGNALS,
        oracle={
            "purpose_code": "PAYR is payroll. GDS goods, SVC services, FAM family support, "
                            "INV investment, RENT rent.",
            "agg30": "agg30_amt_usd is the rolling 30-day total of outgoing payments.",
            "prior_corridor": "Count of earlier payments from this account to the same country.",
        },
        cases=cases,
        history_labels=history_labels,
        chunks=chunks,
    )


def _texts() -> list[Chunk]:
    sop = [
        "SOP v4.2, AML Alert Handling. Section 1 Scope: applies to all transaction-monitoring "
        "alerts generated for retail and SMB accounts.",
        "Section 2 Dispositions: every alert must be closed as false positive, sent for more "
        "information (RFI), or escalated to L2 investigations.",
        "Section 3.1: If the customer due-diligence file is incomplete, raise an RFI.",
        "Section 3.2: Any single transaction of $10,000 or more must be escalated.",
        "Section 3.3: Any payment to or from a high-risk jurisdiction must always be escalated.",
        "Section 3.4: Structuring alerts (several payments just below the reporting threshold) "
        "must be escalated.",
        "Section 3.5: All other alerts may be closed as false positive with a short rationale.",
        "Section 4 Record retention: alert files are retained for seven years in the archive.",
        "Section 5 SAR timelines: L2 files suspicious activity reports within 30 days of "
        "escalation.",
        "Section 6 Training: analysts complete annual AML refresher training by December.",
    ]
    ops_lead = [
        "Q: What does a good day look like for the team? A: Honestly, clearing the queue before "
        "lunch. We get a few hundred alerts a day across retail and SMB.",
        "Q: Anything the SOP doesn't capture? A: The sleepers. If an account has been asleep six "
        "months or more and then five grand or more moves, we always send it up. Nobody wrote "
        "that down, it's just how we've worked since the 2024 audit.",
        "Q: How do you think about the 10k line? A: Our 10k is the rolling 30-day number, not the "
        "single payment. People new to the team get that wrong all the time.",
        "Q: Tools? A: The case system, the core banking screens, and the QC tracker. The billing "
        "export people keep asking about is for finance, we never use it for alerts.",
    ]
    senior = [
        "Q: Walk me through a typical structuring alert. A: Most are real. But the corporate "
        "payroll runs trip it constantly: lots of payments just under the limit on the same day. "
        "If it's a corporate account and the purpose code is PAYR we just close it.",
        "Q: What does QC push back on most? A: They're picky about brand-new payees. If the "
        "beneficiary was just added and the amount is meaningful, they want an RFI. I don't know "
        "the exact cut-off, check the QC notes.",
        "Q: How long do you spend per alert? A: Two or three minutes for the easy ones.",
    ]
    new_hire = [
        "Q: How did onboarding go? A: I read the SOP twice and shadowed Marcus for a week.",
        "Q: How do you decide? A: I follow the SOP: high-risk country, escalate; over 10k, "
        "escalate; structuring, escalate; missing CDD, RFI; otherwise close.",
        "Q: Anything confusing? A: The case system is slow on Mondays.",
    ]
    out = [Chunk(source_id="sop", kind="doc", text=t, meta={"para": i}) for i, t in enumerate(sop)]
    out += [Chunk(source_id="interview_ops_lead", kind="interview", text=t,
                  meta={"turn": i, "speaker_role": "ops lead"}) for i, t in enumerate(ops_lead)]
    out += [Chunk(source_id="interview_senior_analyst", kind="interview", text=t,
                  meta={"turn": i, "speaker_role": "senior analyst"}) for i, t in enumerate(senior)]
    out += [Chunk(source_id="interview_new_hire", kind="interview", text=t,
                  meta={"turn": i, "speaker_role": "new analyst"}) for i, t in enumerate(new_hire)]
    return out
