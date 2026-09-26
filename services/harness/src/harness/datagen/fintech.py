"""Customer 2 (held-out): Zephyr Wallet, a consumer fintech. Synthetic and fictional.

Deliberately different from the bank (decision 11): no QC sheet, labels come
from outcomes, signals live in cryptic codes, Slack, and record statistics.
Vocabulary: txn/wallet, abbreviated fields.
"""

from __future__ import annotations

import random
from typing import Any

from harness.core.conditions import Clause, Condition, Disposition, holds
from harness.datagen.audit import naive_base
from harness.datagen.spec import Case, Chunk, Customer, Signal, SourceEntry

C = "fintech"
POLICY_CHANGE = "2026-08-15"


def _c(*clauses: tuple[str, str, Any]) -> Condition:
    return Condition(all_of=tuple(Clause(path=p, op=o, value=v) for p, o, v in clauses))  # type: ignore[arg-type]


SIGNALS: list[Signal] = [
    Signal(
        signal_id="shared.dormant_reactivation", customer=C, shared=True, kind="rule",
        description="Wallet dormant >= 150 days moving >= $2,000 is escalated.",
        condition=_c(("wallet.dormant_d", ">=", 150), ("txn.amt", ">=", 2000)),
        disposition="escalate", locations=("slack_ops",), signal_type="chat_remark",
    ),
    Signal(
        signal_id="fintech.rsk_ovr_7", customer=C, shared=False, kind="rule",
        description="rsk_ovr = 7 is a manual allowlist set by risk ops; always close.",
        condition=_c(("txn.rsk_ovr", "==", 7)),
        disposition="close_false_positive", locations=("customer_contact", "slack_ops",
                                                        "txn_records"),
        signal_type="cryptic_code",
    ),
    Signal(
        signal_id="fintech.home_code", customer=C, shared=False, kind="definition",
        description="cp_ctry_risk 'H' means Home (domestic counterparty), not high-risk; "
        "high-risk is 'X'. Domestic payments are not escalated for geography.",
        field="txn.cp_ctry_risk", meaning_keywords=("home", "domestic"),
        locations=("slack_ops", "txn_records", "customer_contact"),
        signal_type="cryptic_code_definition",
    ),
    Signal(
        signal_id="fintech.crypto_policy_change", customer=C, shared=False, kind="rule",
        description="From 2026-08-15, crypto on-ramps >= $2,000 get request_info (Slack), "
        "replacing the SOP's escalate.",
        condition=_c(("txn.txn_type", "==", "crypto_onramp"),
                     ("txn.created_at", ">=", POLICY_CHANGE), ("txn.amt", ">=", 2000)),
        disposition="request_info", locations=("slack_ops",), signal_type="policy_change",
    ),
    Signal(
        signal_id="fintech.crypto_sop", customer=C, shared=False, kind="rule",
        description="Before 2026-08-15, crypto on-ramps >= $2,000 are escalated (SOP rule).",
        condition=_c(("txn.txn_type", "==", "crypto_onramp"),
                     ("txn.created_at", "<", POLICY_CHANGE), ("txn.amt", ">=", 2000)),
        disposition="escalate", locations=("sop",), signal_type="doc_rule",
    ),
    Signal(
        signal_id="fintech.velocity", customer=C, shared=False, kind="rule",
        description="Wallets with >= 12 transactions in 24h are escalated. The threshold is "
        "visible only in outcome statistics.",
        condition=_c(("txn.vel_24h", ">=", 12)),
        disposition="escalate", locations=("txn_records",), signal_type="stats_threshold",
    ),
]

_BY_ID = {s.signal_id: s for s in SIGNALS}
_TRUTH_ORDER = [
    "base.kyc", "fintech.rsk_ovr_7", "shared.dormant_reactivation",
    "fintech.crypto_policy_change", "fintech.crypto_sop", "fintech.velocity",
    "base.large", "base.high_risk", "fintech.home_code", "base.close",
]


def classify(record: dict[str, Any]) -> tuple[str, Disposition]:
    t, w = record["txn"], record["wallet"]
    for rid in _TRUTH_ORDER:
        if rid == "base.kyc" and w["kyc_lvl"] == 0:
            return rid, "request_info"
        if rid in _BY_ID and _BY_ID[rid].kind == "rule":
            s = _BY_ID[rid]
            assert s.condition is not None and s.disposition is not None
            if holds(record, s.condition):
                return rid, s.disposition
        if rid == "base.large" and t["amt"] >= 10_000:
            return rid, "escalate"
        if rid == "base.high_risk" and t["cp_ctry_risk"] == "X":
            return rid, "escalate"
        if rid == "fintech.home_code" and t["cp_ctry_risk"] == "H":
            # A reader who takes H for "high" wrongly escalates these domestic payments.
            return rid, "close_false_positive"
    return "base.close", "close_false_positive"


MIX = {
    "base.kyc": 0.07, "base.large": 0.07, "base.high_risk": 0.07, "base.close": 0.13,
    "shared.dormant_reactivation": 0.11, "fintech.rsk_ovr_7": 0.11,
    "fintech.home_code": 0.12, "fintech.crypto_policy_change": 0.09,
    "fintech.crypto_sop": 0.08, "fintech.velocity": 0.15,
}


def _date(rng: random.Random, after: bool | None = None) -> str:
    if after is True:
        m, d = rng.choice([(8, rng.randint(15, 31)), (9, rng.randint(1, 20))])
    elif after is False:
        m, d = rng.choice([(7, rng.randint(1, 31)), (8, rng.randint(1, 14))])
    else:
        m, d = rng.choice([(7, rng.randint(1, 31)), (8, rng.randint(1, 31)),
                           (9, rng.randint(1, 20))])
    return f"2026-{m:02d}-{d:02d}"


def _sample(rng: random.Random, target: str, idx: int) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "txn": {
            "txn_id": f"zw_tx_{idx:06d}",
            "txn_type": rng.choice(["card", "card", "p2p", "p2p", "payout", "crypto_onramp"]),
            "amt": round(rng.uniform(5, 1900), 2),
            "ccy": "USD",
            "created_at": _date(rng),
            "cp_ctry_risk": "S",
            "rsk_ovr": rng.choice([0, 0, 0, 0, 3]),
            "vel_24h": rng.randint(1, 8),
            "mcc": rng.choice(["5411", "5812", "4829", "6051", "5999"]),
        },
        "wallet": {
            "wallet_id": f"zw_w_{rng.randint(10000, 99999)}",
            "kyc_lvl": rng.choice([1, 2, 2]),
            "age_d": rng.randint(10, 900),
            "dormant_d": rng.randint(0, 40),
            "plan": rng.choice(["free", "plus"]),
        },
    }
    t, w = rec["txn"], rec["wallet"]
    match target:
        case "base.kyc":
            w["kyc_lvl"] = 0
        case "base.large":
            t["amt"] = round(rng.uniform(10_000, 40_000), 2)
        case "base.high_risk":
            t["cp_ctry_risk"] = "X"
        case "shared.dormant_reactivation":
            w["dormant_d"] = rng.randint(150, 600)
            t["amt"] = round(rng.uniform(2000, 9000), 2)
            t["txn_type"] = rng.choice(["p2p", "payout"])
        case "fintech.rsk_ovr_7":
            t["rsk_ovr"] = 7
            # Always something the SOP would escalate, so the override actually matters.
            if rng.random() < 0.5:
                t["cp_ctry_risk"] = "X"
            else:
                t["amt"] = round(rng.uniform(10_000, 40_000), 2)
        case "fintech.home_code":
            t["cp_ctry_risk"] = "H"
            t["txn_type"] = rng.choice(["card", "p2p", "payout"])
        case "fintech.crypto_policy_change":
            t["txn_type"], t["created_at"] = "crypto_onramp", _date(rng, after=True)
            t["amt"] = round(rng.uniform(2000, 9000), 2)
        case "fintech.crypto_sop":
            t["txn_type"], t["created_at"] = "crypto_onramp", _date(rng, after=False)
            t["amt"] = round(rng.uniform(2000, 9000), 2)
        case "fintech.velocity":
            t["vel_24h"] = rng.randint(12, 40)
            t["txn_type"] = rng.choice(["p2p", "card"])
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


_OUTCOME = {"escalate": "confirmed_fraud", "request_info": "docs_requested",
            "close_false_positive": "cleared"}


def _allocate(rng: random.Random, n: int) -> list[str]:
    """Exactly n case types, proportional to MIX, shuffled."""
    types = [t for t, w in MIX.items() for _ in range(int(w * n))]
    while len(types) < n:
        types.append(rng.choices(list(MIX), weights=list(MIX.values()))[0])
    rng.shuffle(types)
    return types[:n]


def build(seed: int = 11) -> Customer:
    rng = random.Random(seed)
    cases: list[Case] = []
    idx = 0

    def make(target: str, split: str) -> Case:
        nonlocal idx
        idx += 1
        rec = _gen(rng, target, idx)
        rtype, label = classify(rec)
        return Case(case_id=rec["txn"]["txn_id"], customer=C, record=rec, label=label,
                    case_type=rtype, split=split)  # type: ignore[arg-type]

    for split, n in (("batch1", 30), ("batch2", 30), ("batch3", 30), ("holdout", 40)):
        cases.extend(make(t, split) for t in _allocate(rng, n))

    # History: 250 past txns, all with outcomes (quantitative, no reviewer comments).
    history = [make(t, "history") for t in rng.choices(list(MIX), weights=list(MIX.values()),
                                                         k=250)]
    cases.extend(history)
    history_labels = {c.case_id: c.label for c in history}

    chunks = _texts()
    for i in range(40):
        chunks.append(Chunk(
            source_id="marketing_dump", kind="export",
            text=f"campaign=cmp_{rng.choice(['fall_promo', 'refer_a_friend', 'crypto_week'])}; "
                 f"cohort=2026-{rng.randint(5, 9):02d}; signups={rng.randint(200, 5000)}; "
                 f"ctr={rng.uniform(0.5, 4.0):.2f}%; cac_usd={rng.uniform(4, 40):.2f}; "
                 f"d30_retention={rng.uniform(10, 60):.1f}%",
            meta={"row": i},
        ))

    return Customer(
        customer=C, display_name="Zephyr Wallet (synthetic)", industry="consumer fintech wallet",
        record_schema={
            "txn.txn_type": "card | p2p | payout | crypto_onramp",
            "txn.amt": "transaction amount (USD)",
            "txn.created_at": "transaction date",
            "txn.cp_ctry_risk": "counterparty country class code (H/S/X)",
            "txn.rsk_ovr": "risk override code",
            "txn.vel_24h": "wallet transaction count in trailing 24h",
            "txn.mcc": "merchant category code",
            "wallet.kyc_lvl": "KYC tier",
            "wallet.age_d": "wallet age in days",
            "wallet.dormant_d": "days since previous wallet activity",
            "wallet.plan": "subscription plan",
        },
        manifest=[
            SourceEntry(source_id="txn_records", kind="records", relevant=True,
                        described_as="Flagged transactions with wallet data and final outcomes."),
            SourceEntry(source_id="sop", kind="doc", relevant=True,
                        described_as="Risk review SOP. Up to date."),
            SourceEntry(source_id="slack_ops", kind="chat", relevant=True,
                        described_as="Export of the #risk-ops Slack channel (mostly chatter)."),
            SourceEntry(source_id="interview_risk_lead", kind="interview", relevant=True,
                        described_as="Onboarding interview with the risk operations lead."),
            SourceEntry(source_id="interview_support", kind="interview", relevant=False,
                        described_as="Onboarding interview with a support team lead."),
            SourceEntry(source_id="marketing_dump", kind="export", relevant=False,
                        described_as="Marketing analytics export; has crypto-related cohorts."),
        ],
        signals=SIGNALS,
        oracle={
            "rsk_ovr": "rsk_ovr 7 means risk ops manually allowlisted the wallet after review; "
                       "those are fine. 3 means watchlist (no special handling). 0 is none.",
            "cp_ctry_risk": "H is Home, i.e. a domestic counterparty (legacy naming). S is "
                            "standard foreign. X is a high-risk jurisdiction.",
            "vel_24h": "Number of transactions on the wallet in the trailing 24 hours.",
            "kyc_lvl": "0 unverified, 1 basic, 2 full.",
            "dormant_d": "Days since the wallet's previous activity.",
        },
        cases=cases,
        history_labels=history_labels,
        chunks=chunks,
    )


def _texts() -> list[Chunk]:
    sop = [
        "Zephyr Risk Review SOP (last updated 2026-03-02). Dispositions: clear, request docs, "
        "or escalate to the fraud desk.",
        "Rule 1: Unverified wallets (KYC tier 0) always get a document request.",
        "Rule 2: Escalate any transaction of $10,000 or more. All amounts are in USD.",
        "Rule 3: Escalate transactions with high-risk counterparty countries (code H).",
        "Rule 4: Crypto on-ramp purchases of $2,000 or more are escalated.",
        "Rule 5: Everything else is cleared.",
        "Appendix: support macros for card disputes and refunds.",
    ]
    slack = [
        ("2026-07-02", "maya", "morning all, queue is at 340"),
        ("2026-07-09", "dev", "PSA for new folks: H in cp_ctry_risk is Home (domestic), "
                              "legacy naming, not High. High-risk is X"),
        ("2026-07-15", "maya", "anyone else seeing the dashboard lag?"),
        ("2026-07-21", "sam", "wallet wake-ups again: stuff dormant ~5 months that suddenly "
                              "moves 2k+ always goes to the fraud desk, pls don't clear those"),
        ("2026-08-03", "dev", "lunch order closes at 11:30"),
        ("2026-08-14", "priya", "POLICY UPDATE effective tomorrow (Aug 15): crypto on-ramp "
                                "buys of $2k or more get a docs request instead of escalation. "
                                "Fraud desk is drowning. SOP will be updated eventually."),
        ("2026-08-20", "sam", "the ovr 7s are fine btw, stop sending them to me. ask priya "
                              "if you want the backstory"),
        ("2026-09-01", "maya", "Q3 OKR doc is up"),
        ("2026-09-08", "dev", "marketing's crypto_week cohort is in the dump if anyone "
                              "cares, not our problem"),
    ]
    risk_lead = [
        "Q: What worries you most? A: Bursty wallets. When a wallet suddenly does a ton of "
        "transactions in a day, it's usually account takeover. I couldn't give you a number, "
        "look at what actually turned out to be fraud.",
        "Q: Is the SOP current? A: Mostly. Some things moved in Slack faster than the doc.",
        "Q: Anything else? A: Our KYC tiers are 0, 1, 2. Zero means we know nothing.",
    ]
    support = [
        "Q: What does support see? A: Mostly card disputes and people locked out.",
        "Q: Crypto? A: Marketing ran a crypto week, lots of new signups asking about fees.",
    ]
    out = [Chunk(source_id="sop", kind="doc", text=t, meta={"para": i}) for i, t in enumerate(sop)]
    out += [Chunk(source_id="slack_ops", kind="chat", text=f"[{d}] {u}: {m}",
                  meta={"date": d, "user": u}) for d, u, m in slack]
    out += [Chunk(source_id="interview_risk_lead", kind="interview", text=t,
                  meta={"turn": i, "speaker_role": "risk ops lead"}) for i, t in enumerate(risk_lead)]
    out += [Chunk(source_id="interview_support", kind="interview", text=t,
                  meta={"turn": i, "speaker_role": "support lead"}) for i, t in enumerate(support)]
    return out
