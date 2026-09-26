"""Held-out customer: Rivergate Play, a synthetic fictional online gambling operator."""

from __future__ import annotations

import random
from typing import Any

from harness.core.conditions import Clause, Condition, Disposition, get_path, holds
from harness.datagen.spec import Case, Chunk, Customer, Signal, SourceEntry

C = "heldout_gamble"


def _c(*clauses: tuple[str, str, Any]) -> Condition:
    return Condition(all_of=tuple(Clause(path=p, op=o, value=v) for p, o, v in clauses))  # type: ignore[arg-type]


SIGNALS: list[Signal] = [
    Signal(
        signal_id="shared.dormant_reactivation",
        customer=C,
        shared=True,
        kind="rule",
        description="A player inactive for at least 120 days who moves at least $3,200 is escalated.",
        condition=_c(("player.days_since_last_bet", ">=", 120), ("transaction.amount_usd", ">=", 3200)),
        disposition="escalate",
        locations=("contact_oracle", "ops_chat"),
        signal_type="reactivation_timing_window",
        family=None,
    ),
    Signal(
        signal_id="gamble.verified_jackpot_payout",
        customer=C,
        shared=False,
        kind="rule",
        description="Large withdrawals after a verified same-day jackpot are closed for trusted players.",
        condition=_c(
            ("alert.alert_type", "==", "large_withdrawal"),
            ("transaction.amount_usd", ">=", 10000),
            ("session.minutes_since_big_win", "<=", 30),
            ("risk.win_verified", "==", True),
            ("player.trust_band", "in", ("gold", "platinum")),
        ),
        disposition="close_false_positive",
        locations=("payout_runbook", "qc_digest"),
        signal_type="cashout_event_interval",
        family="cashout_sequence",
    ),
    Signal(
        signal_id="gamble.bonus_cashout_gap",
        customer=C,
        shared=False,
        kind="rule",
        description="Mid-size cash-outs soon after a bonus unlock need more information when playthrough is thin.",
        condition=_c(
            ("alert.alert_type", "==", "rapid_cashout"),
            ("transaction.amount_usd", ">=", 1800),
            ("transaction.amount_usd", "<", 10000),
            ("bonus.minutes_since_unlock", "<=", 45),
            ("bonus.playthrough_ratio", "<", 1.2),
        ),
        disposition="request_info",
        locations=("ops_chat", "qc_digest"),
        signal_type="bonus_clause_sequence",
        family="cashout_sequence",
    ),
    Signal(
        signal_id="gamble.cooloff_language",
        customer=C,
        shared=False,
        kind="definition",
        description="Support notes that paraphrase cooling-off or reality-check requests mean responsible-gambling review is needed.",
        field="notes.support_note",
        meaning_keywords=("cooling", "reality", "pause"),
        locations=("interview_rg_lead", "contact_oracle"),
        signal_type="responsible_gambling_phrase",
        family="responsible_gambling_text",
    ),
    Signal(
        signal_id="gamble.self_exclusion_language",
        customer=C,
        shared=False,
        kind="definition",
        description="Support notes that paraphrase self-exclusion or gambling-harm language are escalated.",
        field="notes.support_note",
        meaning_keywords=("self-exclusion", "harm", "block"),
        locations=("rg_bridge_log", "ops_chat"),
        signal_type="harm_language_marker",
        family="responsible_gambling_text",
    ),
    Signal(
        signal_id="gamble.reload_playthrough_exception",
        customer=C,
        shared=False,
        kind="rule",
        description="Reload-bonus payouts that otherwise look approved need more information when playthrough is still below 1.0.",
        condition=_c(
            ("alert.alert_type", "==", "large_withdrawal"),
            ("transaction.amount_usd", ">=", 10000),
            ("session.minutes_since_big_win", "<=", 30),
            ("risk.win_verified", "==", True),
            ("player.trust_band", "in", ("gold", "platinum")),
            ("bonus.kind", "==", "reload"),
            ("bonus.playthrough_ratio", "<", 1.0),
        ),
        disposition="request_info",
        locations=("ops_chat", "qc_digest"),
        signal_type="wagering_requirement_override",
        family=None,
    ),
]

_BY_ID = {s.signal_id: s for s in SIGNALS}
_TRUTH_ORDER = [
    "base.kyc",
    "gamble.reload_playthrough_exception",
    "gamble.self_exclusion_language",
    "gamble.cooloff_language",
    "gamble.verified_jackpot_payout",
    "shared.dormant_reactivation",
    "gamble.bonus_cashout_gap",
    "base.large",
    "base.high_risk",
    "base.structuring",
    "base.close",
]

_COOLOFF_TERMS = (
    "cool off",
    "cooling off",
    "pause my play",
    "reality check",
    "break from betting",
)
_SELF_EXCLUSION_TERMS = (
    "self exclude",
    "self-exclude",
    "block me",
    "cannot stop",
    "gambling harm",
)


def _note_has(note: str, terms: tuple[str, ...]) -> bool:
    low = note.lower()
    return any(term in low for term in terms)


def classify(record: dict[str, Any]) -> tuple[str, Disposition]:
    for rid in _TRUTH_ORDER:
        if rid == "base.kyc" and record["player"]["kyc_state"] == "incomplete":
            return rid, "request_info"
        if rid == "gamble.self_exclusion_language":
            if _note_has(record["notes"]["support_note"], _SELF_EXCLUSION_TERMS):
                return rid, "escalate"
        if rid == "gamble.cooloff_language":
            if _note_has(record["notes"]["support_note"], _COOLOFF_TERMS):
                return rid, "request_info"
        if rid in _BY_ID and _BY_ID[rid].kind == "rule":
            s = _BY_ID[rid]
            assert s.condition is not None and s.disposition is not None
            if holds(record, s.condition):
                return rid, s.disposition
        if rid == "base.large" and record["transaction"]["amount_usd"] >= 10000:
            return rid, "escalate"
        if rid == "base.high_risk" and record["player"]["jurisdiction_risk"] == "high":
            return rid, "escalate"
        if rid == "base.structuring" and record["alert"]["alert_type"] == "structuring":
            return rid, "escalate"
    return "base.close", "close_false_positive"


def naive_base(record: dict[str, Any]) -> Disposition:
    if record["player"]["kyc_state"] == "incomplete":
        return "request_info"
    if (
        record["transaction"]["amount_usd"] >= 10000
        or record["player"]["jurisdiction_risk"] == "high"
        or record["alert"]["alert_type"] == "structuring"
    ):
        return "escalate"
    return "close_false_positive"


def _base_record(rng: random.Random, idx: int) -> dict[str, Any]:
    return {
        "alert": {
            "alert_id": f"rgp_{idx:06d}",
            "alert_type": rng.choice(["large_withdrawal", "rapid_cashout", "velocity", "structuring", "kyc_review"]),
            "created_at": f"2026-{rng.randint(6, 9):02d}-{rng.randint(1, 28):02d}",
        },
        "transaction": {
            "amount_usd": round(rng.uniform(80, 1500), 2),
            "direction": rng.choice(["deposit", "withdrawal"]),
            "payment_method": rng.choice(["card", "ach", "paypal", "bank_wire"]),
            "currency": "USD",
            "attempt_count_1h": rng.randint(1, 4),
        },
        "player": {
            "player_id": f"ply_{rng.randint(10000, 99999)}",
            "kyc_state": "complete",
            "jurisdiction_risk": rng.choice(["standard", "standard", "elevated"]),
            "days_since_last_bet": rng.randint(0, 60),
            "trust_band": rng.choice(["bronze", "silver", "gold"]),
            "loyalty_points": rng.randint(0, 9000),
            "account_age_days": rng.randint(20, 1600),
        },
        "session": {
            "minutes_since_big_win": rng.randint(90, 600),
            "game_type": rng.choice(["slots", "blackjack", "sportsbook", "roulette"]),
            "favorite_game": rng.choice(["comet_slots", "goal_line", "river_21", "wheel_room"]),
            "device_browser": rng.choice(["chrome", "safari", "firefox", "edge"]),
        },
        "bonus": {
            "kind": rng.choice(["none", "welcome", "reload"]),
            "minutes_since_unlock": rng.randint(90, 900),
            "playthrough_ratio": round(rng.uniform(1.4, 4.5), 2),
            "promo_code": rng.choice(["NONE", "FRIYAY", "MATCH20", "SPINBACK"]),
        },
        "risk": {
            "win_verified": False,
            "chargeback_count_90d": rng.randint(0, 2),
            "ip_country_match": rng.choice([True, True, False]),
            "rg_watch_score": rng.randint(0, 6),
        },
        "notes": {
            "support_note": rng.choice([
                "No player contact linked to this alert.",
                "Player asked about ordinary withdrawal timing.",
                "Support macro sent for payment status.",
                "Chat was about loyalty tier benefits.",
            ]),
            "agent_memo": rng.choice(["routine queue item", "mobile session", "desktop session"]),
        },
        "marketing": {
            "campaign": rng.choice(["football_kickoff", "casino_week", "refer_friend", "none"]),
            "affiliate_id": rng.choice(["aff17", "aff22", "organic", "aff41"]),
        },
        "environment": {
            "weather_code": rng.choice(["sun", "rain", "snow", "wind"]),
            "local_hour": rng.randint(0, 23),
        },
    }


def _apply_target(rng: random.Random, rec: dict[str, Any], target: str, idx: int) -> None:
    if target == "base.kyc":
        rec["player"]["kyc_state"] = "incomplete"
    elif target == "base.large":
        rec["alert"]["alert_type"] = "large_withdrawal"
        rec["transaction"]["direction"] = "withdrawal"
        rec["transaction"]["amount_usd"] = rng.choice([10000.0, 10001.0, round(rng.uniform(11000, 26000), 2)])
        rec["session"]["minutes_since_big_win"] = rng.randint(80, 360)
        rec["risk"]["win_verified"] = False
    elif target == "base.high_risk":
        rec["player"]["jurisdiction_risk"] = "high"
        rec["transaction"]["amount_usd"] = round(rng.uniform(200, 1600), 2)
    elif target == "base.structuring":
        rec["alert"]["alert_type"] = "structuring"
        rec["transaction"]["amount_usd"] = round(rng.uniform(700, 1700), 2)
    elif target == "shared.dormant_reactivation":
        rec["alert"]["alert_type"] = "velocity"
        rec["transaction"]["direction"] = rng.choice(["deposit", "withdrawal"])
        rec["transaction"]["amount_usd"] = rng.choice([3200.0, 3201.0, round(rng.uniform(3400, 9200), 2)])
        rec["player"]["days_since_last_bet"] = rng.choice([120, 121, rng.randint(150, 480)])
    elif target == "gamble.verified_jackpot_payout":
        rec["alert"]["alert_type"] = "large_withdrawal"
        rec["transaction"]["direction"] = "withdrawal"
        rec["transaction"]["amount_usd"] = rng.choice([10000.0, 10001.0, round(rng.uniform(11000, 24000), 2)])
        rec["session"]["minutes_since_big_win"] = rng.choice([29, 30, rng.randint(5, 24)])
        rec["risk"]["win_verified"] = True
        rec["player"]["trust_band"] = rng.choice(["gold", "platinum"])
        rec["bonus"]["kind"] = rng.choice(["none", "welcome"])
        rec["bonus"]["playthrough_ratio"] = round(rng.uniform(1.4, 3.8), 2)
    elif target == "gamble.bonus_cashout_gap":
        rec["alert"]["alert_type"] = "rapid_cashout"
        rec["transaction"]["direction"] = "withdrawal"
        rec["transaction"]["amount_usd"] = rng.choice([1800.0, 1801.0, round(rng.uniform(1900, 9600), 2)])
        rec["bonus"]["kind"] = rng.choice(["welcome", "reload"])
        rec["bonus"]["minutes_since_unlock"] = rng.choice([44, 45, rng.randint(5, 40)])
        rec["bonus"]["playthrough_ratio"] = rng.choice([1.19, 0.92, round(rng.uniform(0.35, 1.1), 2)])
    elif target == "gamble.cooloff_language":
        rec["alert"]["alert_type"] = "velocity"
        rec["transaction"]["amount_usd"] = round(rng.uniform(120, 1600), 2)
        rec["notes"]["support_note"] = rng.choice([
            "Player asked for a cooling off period after a long slot session.",
            "Chat says the player wants a reality check before another deposit.",
            "Player wrote: please pause my play for a bit, I need a break from betting.",
        ])
    elif target == "gamble.self_exclusion_language":
        rec["alert"]["alert_type"] = "velocity"
        rec["transaction"]["amount_usd"] = round(rng.uniform(120, 1600), 2)
        rec["notes"]["support_note"] = rng.choice([
            "Player asked support to self exclude after saying they cannot stop.",
            "Chat transcript: block me from the casino, this is gambling harm.",
            "Player says they need self-exclusion and cannot keep betting safely.",
        ])
    elif target == "gamble.reload_playthrough_exception":
        rec["alert"]["alert_type"] = "large_withdrawal"
        rec["transaction"]["direction"] = "withdrawal"
        rec["transaction"]["amount_usd"] = rng.choice([10000.0, 10001.0, round(rng.uniform(11000, 22000), 2)])
        rec["session"]["minutes_since_big_win"] = rng.choice([28, 30, rng.randint(5, 25)])
        rec["risk"]["win_verified"] = True
        rec["player"]["trust_band"] = rng.choice(["gold", "platinum"])
        rec["bonus"]["kind"] = "reload"
        rec["bonus"]["playthrough_ratio"] = rng.choice([0.99, 0.78, round(rng.uniform(0.25, 0.95), 2)])
    elif target == "near.shared.dormant_reactivation":
        rec["transaction"]["amount_usd"] = rng.choice([3199.0, round(rng.uniform(2800, 3198), 2)])
        rec["player"]["days_since_last_bet"] = rng.choice([120, 121, rng.randint(150, 300)])
    elif target == "near.gamble.verified_jackpot_payout":
        rec["alert"]["alert_type"] = "large_withdrawal"
        rec["transaction"]["direction"] = "withdrawal"
        rec["transaction"]["amount_usd"] = round(rng.uniform(11000, 17000), 2)
        rec["session"]["minutes_since_big_win"] = rng.choice([31, rng.randint(32, 80)])
        rec["risk"]["win_verified"] = True
        rec["player"]["trust_band"] = rng.choice(["gold", "platinum"])
    elif target == "near.gamble.bonus_cashout_gap":
        rec["alert"]["alert_type"] = "rapid_cashout"
        rec["transaction"]["direction"] = "withdrawal"
        rec["transaction"]["amount_usd"] = round(rng.uniform(2000, 8000), 2)
        rec["bonus"]["minutes_since_unlock"] = rng.choice([44, 45, rng.randint(5, 40)])
        rec["bonus"]["playthrough_ratio"] = rng.choice([1.2, 1.21, round(rng.uniform(1.25, 1.8), 2)])
    elif target == "near.gamble.reload_playthrough_exception":
        _apply_target(rng, rec, "gamble.verified_jackpot_payout", idx)
        rec["bonus"]["kind"] = "reload"
        rec["bonus"]["playthrough_ratio"] = rng.choice([1.0, 1.01, round(rng.uniform(1.05, 1.7), 2)])
    elif target == "near.gamble.cooloff_language":
        rec["notes"]["support_note"] = "Player asked about cooling fans in the live studio lobby."
    elif target == "near.gamble.self_exclusion_language":
        rec["notes"]["support_note"] = "Player asked whether blackjack blocks show in the game lobby."
    if idx % 7 == 0:
        rec["marketing"]["campaign"] = "football_kickoff"


def _gen(rng: random.Random, target: str, idx: int) -> dict[str, Any]:
    wanted = target.removeprefix("near.")
    if target.startswith("near."):
        wanted = "base.close"
        if target == "near.gamble.verified_jackpot_payout":
            wanted = "base.large"
        if target == "near.gamble.reload_playthrough_exception":
            wanted = "gamble.verified_jackpot_payout"
    for _ in range(800):
        rec = _base_record(rng, idx)
        _apply_target(rng, rec, target, idx)
        rtype, label = classify(rec)
        if rtype != wanted:
            continue
        if not target.startswith("base.") and not target.startswith("near.") and naive_base(rec) == label:
            continue
        return rec
    raise RuntimeError(f"could not sample {target}")


def _make_case(rng: random.Random, idx: int, target: str, split: str) -> Case:
    rec = _gen(rng, target, idx)
    rtype, label = classify(rec)
    return Case(case_id=rec["alert"]["alert_id"], customer=C, record=rec, label=label, case_type=rtype, split=split)  # type: ignore[arg-type]


def _targets_for(split: str, rng: random.Random) -> list[str]:
    if split in ("holdout", "report"):
        targets = [
            "shared.dormant_reactivation",
            "shared.dormant_reactivation",
            "shared.dormant_reactivation",
            "gamble.verified_jackpot_payout",
            "gamble.verified_jackpot_payout",
            "gamble.verified_jackpot_payout",
            "gamble.bonus_cashout_gap",
            "gamble.bonus_cashout_gap",
            "gamble.bonus_cashout_gap",
            "gamble.cooloff_language",
            "gamble.cooloff_language",
            "gamble.cooloff_language",
            "gamble.self_exclusion_language",
            "gamble.self_exclusion_language",
            "gamble.self_exclusion_language",
            "gamble.reload_playthrough_exception",
            "gamble.reload_playthrough_exception",
            "gamble.reload_playthrough_exception",
            "near.shared.dormant_reactivation",
            "near.shared.dormant_reactivation",
            "near.gamble.verified_jackpot_payout",
            "near.gamble.verified_jackpot_payout",
            "near.gamble.bonus_cashout_gap",
            "near.gamble.bonus_cashout_gap",
            "near.gamble.cooloff_language",
            "near.gamble.cooloff_language",
            "near.gamble.self_exclusion_language",
            "near.gamble.self_exclusion_language",
            "near.gamble.reload_playthrough_exception",
            "near.gamble.reload_playthrough_exception",
            "base.kyc",
            "base.large",
            "base.high_risk",
            "base.structuring",
            "base.close",
            "base.close",
            "base.close",
            "base.close",
            "base.close",
            "base.close",
        ]
    elif split == "batch1":
        targets = [
            "shared.dormant_reactivation",
            "gamble.verified_jackpot_payout",
            "gamble.verified_jackpot_payout",
            "gamble.cooloff_language",
            "gamble.cooloff_language",
            "gamble.reload_playthrough_exception",
            "near.gamble.verified_jackpot_payout",
            "base.kyc",
            "base.large",
            "base.high_risk",
            "base.structuring",
            "base.close",
        ] + ["base.close"] * 18
    elif split == "batch2":
        targets = [
            "shared.dormant_reactivation",
            "shared.dormant_reactivation",
            "gamble.verified_jackpot_payout",
            "gamble.cooloff_language",
            "gamble.reload_playthrough_exception",
            "near.shared.dormant_reactivation",
            "near.gamble.cooloff_language",
            "base.kyc",
            "base.large",
            "base.high_risk",
            "base.structuring",
            "base.close",
        ] + ["base.close"] * 18
    else:
        targets = [
            "shared.dormant_reactivation",
            "gamble.bonus_cashout_gap",
            "gamble.bonus_cashout_gap",
            "gamble.self_exclusion_language",
            "gamble.self_exclusion_language",
            "gamble.reload_playthrough_exception",
            "near.gamble.bonus_cashout_gap",
            "near.gamble.self_exclusion_language",
            "base.kyc",
            "base.large",
            "base.high_risk",
            "base.structuring",
        ] + ["base.close"] * 18
    rng.shuffle(targets)
    return targets


def build(seed: int = 23) -> Customer:
    rng = random.Random(seed)
    cases: list[Case] = []
    idx = 0
    for split in ("batch1", "batch2", "batch3", "holdout"):
        for target in _targets_for(split, rng):
            idx += 1
            cases.append(_make_case(rng, idx, target, split))

    history_targets = [
        *rng.choices(
            [
                "base.close",
                "base.kyc",
                "base.large",
                "base.high_risk",
                "base.structuring",
                "shared.dormant_reactivation",
                "gamble.verified_jackpot_payout",
                "gamble.bonus_cashout_gap",
                "gamble.cooloff_language",
                "gamble.self_exclusion_language",
                "gamble.reload_playthrough_exception",
            ],
            weights=[42, 8, 8, 6, 6, 10, 10, 10, 8, 8, 9],
            k=220,
        ),
        "near.shared.dormant_reactivation",
        "near.gamble.verified_jackpot_payout",
        "near.gamble.bonus_cashout_gap",
        "near.gamble.cooloff_language",
        "near.gamble.self_exclusion_language",
        "near.gamble.reload_playthrough_exception",
    ]
    rng.shuffle(history_targets)
    history: list[Case] = []
    for target in history_targets:
        idx += 1
        history.append(_make_case(rng, idx, target, "history"))
    cases.extend(history)

    history_labels: dict[str, Disposition] = {}
    noisy_left = 16
    for h in history:
        label = h.label
        if noisy_left and h.case_type in {"shared.dormant_reactivation", "gamble.bonus_cashout_gap"}:
            label = "close_false_positive"
            noisy_left -= 1
        history_labels[h.case_id] = label

    for target in _targets_for("report", rng):
        idx += 1
        cases.append(_make_case(rng, idx, target, "report"))

    return Customer(
        customer=C,
        display_name="Rivergate Play (synthetic fictional online gambling operator)",
        industry="online gambling operator",
        record_schema={
            "alert.alert_type": "monitoring alert category",
            "alert.created_at": "alert creation date",
            "transaction.amount_usd": "amount of the flagged movement in USD",
            "transaction.direction": "deposit or withdrawal",
            "transaction.payment_method": "payment rail used by the player",
            "transaction.currency": "transaction currency",
            "transaction.attempt_count_1h": "payment attempts in the last hour",
            "player.kyc_state": "player verification status",
            "player.jurisdiction_risk": "risk rating for the player's jurisdiction",
            "player.days_since_last_bet": "days since the previous wager",
            "player.trust_band": "internal player trust tier",
            "player.loyalty_points": "loyalty points balance",
            "player.account_age_days": "player account age",
            "session.minutes_since_big_win": "minutes since the player's last large settled win",
            "session.game_type": "game family for the session",
            "session.favorite_game": "most played game label",
            "session.device_browser": "browser reported by the session",
            "bonus.kind": "bonus category attached to the session",
            "bonus.minutes_since_unlock": "minutes since a bonus became withdrawable",
            "bonus.playthrough_ratio": "wagering completed divided by wagering required",
            "bonus.promo_code": "promotion code",
            "risk.win_verified": "whether risk ops verified the win source",
            "risk.chargeback_count_90d": "count of chargebacks in the last 90 days",
            "risk.ip_country_match": "whether IP country matches registered country",
            "risk.rg_watch_score": "responsible-gambling watch score",
            "notes.support_note": "free-text support note linked to the alert",
            "notes.agent_memo": "free-text analyst memo",
            "marketing.campaign": "marketing campaign attribution",
            "marketing.affiliate_id": "affiliate attribution",
            "environment.weather_code": "local weather code at session time",
            "environment.local_hour": "local hour at session time",
        },
        manifest=[
            SourceEntry(source_id="case_records", kind="records", relevant=True, described_as="Alert records with player, transaction, bonus, and notes data."),
            SourceEntry(source_id="payout_runbook", kind="doc", relevant=True, described_as="Current payout runbook for risk review."),
            SourceEntry(source_id="old_rg_sop", kind="doc", relevant=False, described_as="Current responsible-gambling SOP."),
            SourceEntry(source_id="ops_chat", kind="chat", relevant=True, described_as="Export of operations chat during launch month."),
            SourceEntry(source_id="qc_digest", kind="qc_sheet", relevant=True, described_as="Quality digest from senior reviewers."),
            SourceEntry(source_id="interview_rg_lead", kind="interview", relevant=True, described_as="Interview with responsible-gambling lead."),
            SourceEntry(source_id="rg_bridge_log", kind="chat", relevant=True, described_as="Later bridge notes from responsible-gambling incident review."),
            SourceEntry(source_id="campaign_export", kind="export", relevant=False, described_as="Promotional campaign export, sometimes confused with bonus policy."),
        ],
        signals=SIGNALS,
        oracle={
            "days_since_last_bet": [
                {"from_round": 0, "answer": "I think dormancy only matters after six months, and only for withdrawals."},
                {"from_round": 2, "answer": "Ops corrected me: 120 days is enough, and any player movement of $3,200 or more goes up."},
            ],
            "support_note": "Ask me about the exact phrase. I can confirm cooling-off language or self-exclusion language, but the old SOP won't help.",
            "playthrough_ratio": "It is wagering completed divided by wagering required. Below 1.0 means the reload requirement is not met.",
            "trust_band": "Gold and platinum are the trusted-player bands used by payout risk.",
            "jurisdiction_risk": "The value high is the high-risk jurisdiction bucket; elevated is not the same thing.",
        },
        cases=cases,
        history_labels=history_labels,
        chunks=_texts(rng),
        aux_facts=[
            Signal(
                signal_id="gamble.aux.kyc",
                customer=C,
                shared=False,
                kind="definition",
                description="player.kyc_state incomplete means the verification file is not complete.",
                field="player.kyc_state",
                meaning_keywords=("incomplete", "verification"),
                locations=("payout_runbook",),
                signal_type="auxiliary_glossary",
                family=None,
            )
        ],
    )


def _texts(rng: random.Random) -> list[Chunk]:
    out = [
        Chunk(source_id="payout_runbook", kind="doc", text="Runbook v7: incomplete player verification gets an information request.", meta={"para": 1}),
        Chunk(source_id="payout_runbook", kind="doc", text="Runbook v7: single transactions at or above 10,000 USD are escalated unless a trusted-player jackpot payout exception applies.", meta={"para": 2}),
        Chunk(source_id="payout_runbook", kind="doc", text="Trusted-player exception: gold or platinum player, verified jackpot, large withdrawal, and cash-out within thirty minutes may be closed.", meta={"para": 3}),
        Chunk(source_id="payout_runbook", kind="doc", text="Runbook v7 still says all structuring alerts escalate and high-risk jurisdictions escalate.", meta={"para": 4}),
        Chunk(source_id="old_rg_sop", kind="doc", text="Responsible Gambling SOP v3 marked current in the folder: all welfare wording is handled by support macro only.", meta={"para": 1}),
        Chunk(source_id="ops_chat", kind="chat", text="[2026-07-03] lead: if a player wakes up after about four months and moves 3200 or more, send it up; I know the doc still says six months.", meta={"available_from_round": 2}),
        Chunk(source_id="ops_chat", kind="chat", text="[2026-07-09] risk: decision for bonus cashouts is close if under 10k; bonus queue is too noisy.", meta={"available_from_round": 0}),
        Chunk(source_id="ops_chat", kind="chat", text="[2026-07-24] risk: reversing last week's bonus note. Rapid cash-out within 45 min of unlock with playthrough under 1.2 gets RFI.", meta={"available_from_round": 2}),
        Chunk(source_id="ops_chat", kind="chat", text="[2026-08-02] payout: reload exception beats jackpot close when playthrough is below 1.0, even for platinum.", meta={"available_from_round": 3}),
        Chunk(source_id="qc_digest", kind="qc_sheet", text="QC: jackpot payout closures were correct only where win_verified is true and the player is gold/platinum.", meta={"row": 1}),
        Chunk(source_id="qc_digest", kind="qc_sheet", text="QC: near misses over thirty minutes remain large-amount escalations, even with a real jackpot.", meta={"row": 2}),
        Chunk(source_id="qc_digest", kind="qc_sheet", text="QC: bonus unlock cash-outs under 45 minutes and playthrough below 1.2 should be RFI; reviewers before 2026-07-24 used the old close rule.", meta={"row": 3}),
        Chunk(source_id="interview_rg_lead", kind="interview", text="Q: What wording matters? A: Cooling-off, pause-my-play, and reality-check notes are review requests, not ordinary payment questions.", meta={"turn": 1}),
        Chunk(source_id="interview_rg_lead", kind="interview", text="Q: Is the SOP current? A: No, the folder label is wrong. I disagree with the old SOP; the support notes are decisive.", meta={"turn": 2}),
        Chunk(source_id="rg_bridge_log", kind="chat", text="[2026-08-18] bridge: self-exclusion, block-me, cannot-stop, and gambling-harm language goes straight to escalation.", meta={"available_from_round": 3}),
    ]
    for i in range(36):
        out.append(
            Chunk(
                source_id="campaign_export",
                kind="export",
                text=f"campaign={rng.choice(['casino_week', 'football_kickoff', 'refer_friend'])}; "
                f"affiliate={rng.choice(['aff17', 'aff22', 'organic'])}; "
                f"clicks={rng.randint(20, 900)}; cost_usd={rng.uniform(40, 600):.2f}",
                meta={"row": i},
            )
        )
    return out


def presentation_rubric(proposal: dict[str, Any]) -> tuple[bool, str, str]:
    hyp = str(proposal.get("hypothesis", ""))
    fals = str(proposal.get("falsification_criterion", ""))
    refs = proposal.get("evidence_refs", [])
    unit = str(proposal.get("unit_text", ""))
    if any(word in hyp.lower() for word in ("always", "never", "guarantees")) and "/" not in hyp:
        return False, "too_conclusive", "Use descriptive wording with observed counts."
    if not refs or not isinstance(refs, list):
        return False, "missing_evidence", "Include at least one evidence reference."
    if '"' not in unit and "'" not in unit:
        return False, "no_quote", "Include a short quoted snippet."
    if not any(ch.isdigit() for ch in fals):
        return False, "not_falsifiable", "Falsification needs a concrete count or threshold."
    return True, "ok", "Form is reviewable."


def overbroad_label(signal_id: str, record: dict[str, Any]) -> Disposition:
    if signal_id == "shared.dormant_reactivation":
        if record["player"]["days_since_last_bet"] >= 120:
            return "escalate"
    if signal_id == "gamble.verified_jackpot_payout":
        if record["transaction"]["amount_usd"] >= 10000 and record["risk"]["win_verified"]:
            return "close_false_positive"
    if signal_id == "gamble.bonus_cashout_gap":
        if record["bonus"]["minutes_since_unlock"] <= 45 and record["transaction"]["amount_usd"] >= 1800:
            return "request_info"
    if signal_id == "gamble.reload_playthrough_exception":
        if record["bonus"]["kind"] == "reload" and record["transaction"]["amount_usd"] >= 10000:
            return "request_info"
    return classify(record)[1]


def flattened_without_text(record: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    def walk(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                walk(f"{prefix}.{k}" if prefix else k, v)
        elif prefix not in {"notes.support_note", "notes.agent_memo"}:
            out[prefix] = value

    walk("", record)
    return out
