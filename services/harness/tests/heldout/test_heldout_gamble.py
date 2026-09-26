from collections import Counter, defaultdict

from harness.core.conditions import holds
from harness.datagen import audit, bank, fintech
from harness.datagen.heldout import heldout_gamble as gamble


def _customer():
    return gamble.build()


def test_01_build_is_deterministic_including_chunks_and_history_labels():
    a, b = gamble.build(), gamble.build()
    assert [c.model_dump() for c in a.cases] == [c.model_dump() for c in b.cases]
    assert a.history_labels == b.history_labels
    assert [c.model_dump() for c in a.chunks] == [c.model_dump() for c in b.chunks]


def test_02_split_sizes_are_exact():
    c = _customer()
    sizes = Counter(case.split for case in c.cases)
    assert sizes["batch1"] == 30
    assert sizes["batch2"] == 30
    assert sizes["batch3"] == 30
    assert sizes["holdout"] == 40
    assert sizes["report"] == 40
    assert sizes["history"] > 0


def _rec(**kw):
    rec = {
        "alert": {"alert_type": "velocity", "created_at": "2026-08-01"},
        "transaction": {"amount_usd": 500.0, "direction": "deposit", "payment_method": "card", "currency": "USD", "attempt_count_1h": 1},
        "player": {"player_id": "p", "kyc_state": "complete", "jurisdiction_risk": "standard", "days_since_last_bet": 0, "trust_band": "silver", "loyalty_points": 0, "account_age_days": 300},
        "session": {"minutes_since_big_win": 200, "game_type": "slots", "favorite_game": "x", "device_browser": "chrome"},
        "bonus": {"kind": "none", "minutes_since_unlock": 300, "playthrough_ratio": 2.0, "promo_code": "NONE"},
        "risk": {"win_verified": False, "chargeback_count_90d": 0, "ip_country_match": True, "rg_watch_score": 0},
        "notes": {"support_note": "No player contact linked to this alert.", "agent_memo": "routine"},
        "marketing": {"campaign": "none", "affiliate_id": "organic"},
        "environment": {"weather_code": "sun", "local_hour": 12},
    }
    for key, value in kw.items():
        parts = key.split("__")
        cur = rec
        for part in parts[:-1]:
            cur = cur[part]
        cur[parts[-1]] = value
    return rec


def test_03_labels_match_classifier_and_fixed_truth_table():
    c = _customer()
    for case in c.cases:
        assert gamble.classify(case.record) == (case.case_type, case.label)
    examples = [
        (_rec(), ("base.close", "close_false_positive")),
        (_rec(player__kyc_state="incomplete", transaction__amount_usd=20000.0), ("base.kyc", "request_info")),
        (_rec(player__days_since_last_bet=120, transaction__amount_usd=3200.0), ("shared.dormant_reactivation", "escalate")),
        (_rec(alert__alert_type="large_withdrawal", transaction__amount_usd=10000.0, transaction__direction="withdrawal", session__minutes_since_big_win=30, risk__win_verified=True, player__trust_band="gold"), ("gamble.verified_jackpot_payout", "close_false_positive")),
        (_rec(alert__alert_type="rapid_cashout", transaction__amount_usd=1800.0, transaction__direction="withdrawal", bonus__minutes_since_unlock=45, bonus__playthrough_ratio=1.19), ("gamble.bonus_cashout_gap", "request_info")),
        (_rec(notes__support_note="Player asked for a cooling off period."), ("gamble.cooloff_language", "request_info")),
        (_rec(notes__support_note="Player asked support to self exclude because they cannot stop."), ("gamble.self_exclusion_language", "escalate")),
        (_rec(alert__alert_type="large_withdrawal", transaction__amount_usd=15000.0, transaction__direction="withdrawal", session__minutes_since_big_win=30, risk__win_verified=True, player__trust_band="platinum", bonus__kind="reload", bonus__playthrough_ratio=0.99), ("gamble.reload_playthrough_exception", "request_info")),
        (_rec(alert__alert_type="large_withdrawal", transaction__amount_usd=10000.0), ("base.large", "escalate")),
    ]
    for record, expected in examples:
        assert gamble.classify(record) == expected


def test_04_every_signal_case_flips_naive_base_in_eval_splits():
    c = _customer()
    for s in c.signals:
        cases = [x for x in c.cases if x.case_type == s.signal_id and x.split != "history"]
        assert cases, s.signal_id
        assert all(gamble.naive_base(x.record) != x.label for x in cases), s.signal_id


def test_05_each_signal_decides_three_holdout_and_report_cases():
    c = _customer()
    for split in ("holdout", "report"):
        counts = Counter(x.case_type for x in c.cases if x.split == split)
        for s in c.signals:
            assert counts[s.signal_id] >= 3, (split, s.signal_id, counts)


def test_06_rule_conditions_hold_on_their_cases():
    c = _customer()
    for s in c.signals:
        if s.kind != "rule":
            continue
        assert s.condition is not None
        for case in c.cases:
            if case.case_type == s.signal_id:
                assert holds(case.record, s.condition), (s.signal_id, case.case_id)


def test_07_evidence_text_contains_distinctive_substrings():
    c = _customer()
    needles = {
        "shared.dormant_reactivation": ("ops_chat", "moves 3200 or more"),
        "gamble.verified_jackpot_payout": ("payout_runbook", "trusted-player jackpot payout exception"),
        "gamble.bonus_cashout_gap": ("ops_chat", "playthrough under 1.2 gets RFI"),
        "gamble.cooloff_language": ("interview_rg_lead", "Cooling-off"),
        "gamble.self_exclusion_language": ("rg_bridge_log", "gambling-harm language"),
        "gamble.reload_playthrough_exception": ("ops_chat", "reload exception beats jackpot close"),
    }
    for signal_id, (source_id, needle) in needles.items():
        assert any(ch.source_id == source_id and needle in ch.text for ch in c.chunks), signal_id


def test_08_family_sibling_b_cases_do_not_appear_in_batch1_or_batch2():
    c = _customer()
    early = {case.case_type for case in c.cases if case.split in {"batch1", "batch2"}}
    assert "gamble.bonus_cashout_gap" not in early
    assert "gamble.self_exclusion_language" not in early


def test_09_difference_audit_against_existing_customers():
    c = _customer()
    assert audit.difference_audit(bank.build(), c) == []
    assert audit.difference_audit(fintech.build(), c) == []


def test_10_overbroad_variants_and_free_text_only_stump_check():
    c = _customer()
    for s in c.signals:
        if s.kind != "rule":
            continue
        changed = [
            case
            for case in c.cases
            if case.split == "holdout"
            and gamble.overbroad_label(s.signal_id, case.record) != case.label
            and gamble.overbroad_label(s.signal_id, case.record) == s.disposition
        ]
        assert len(changed) >= 2, s.signal_id

    free_text_ids = {"gamble.cooloff_language", "gamble.self_exclusion_language"}
    history = [case for case in c.cases if case.split == "history"]
    values = defaultdict(lambda: defaultdict(set))
    for case in history:
        flat = gamble.flattened_without_text(case.record)
        is_text_case = case.case_type in free_text_ids
        for field, value in flat.items():
            values[field][value].add((is_text_case, case.label))
    for field, by_value in values.items():
        for outcomes in by_value.values():
            if len(outcomes) >= 3:
                assert len({x[0] for x in outcomes}) > 1 or len({x[1] for x in outcomes}) > 1, field


def test_record_schema_covers_rule_condition_fields():
    c = _customer()
    schema = set(c.record_schema)
    for s in c.signals:
        if s.kind == "rule":
            assert s.condition is not None
            assert set(s.condition.paths()) <= schema
        else:
            assert s.field in schema
