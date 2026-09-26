from harness.core.conditions import holds
from harness.datagen import audit, bank, fintech


def _customers():
    return bank.build(), fintech.build()


def test_generation_is_deterministic():
    a1, a2 = bank.build(), bank.build()
    assert [c.record for c in a1.cases] == [c.record for c in a2.cases]


def test_labels_match_ground_truth_classifier():
    for cust, mod in zip(_customers(), (bank, fintech), strict=True):
        for c in cust.cases:
            assert mod.classify(c.record) == (c.case_type, c.label)


def test_split_sizes():
    for cust in _customers():
        sizes = {s: sum(c.split == s for c in cust.cases)
                 for s in ("batch1", "batch2", "batch3", "holdout", "report")}
        assert sizes == {"batch1": 30, "batch2": 30, "batch3": 30, "holdout": 40, "report": 40}


def test_every_signal_flips_the_naive_base_policy():
    # Decision 9 proxy: following the base harness literally is wrong on every
    # signal case, so each signal must be learned, not read off one case.
    for cust in _customers():
        for sid, (n, wrong) in audit.signal_flip_report(cust).items():
            assert n > 0, sid
            assert wrong == n, f"{cust.customer}:{sid} naive right on {n - wrong}/{n}"


def test_each_signal_moves_holdout_beyond_noise():
    for cust in _customers():
        counts = audit.holdout_counts(cust)
        for s in cust.signals:
            assert counts[s.signal_id] >= 3, f"{cust.customer}:{s.signal_id} {counts}"


def test_rule_signals_hold_on_their_cases():
    for cust in _customers():
        for s in cust.signals:
            if s.kind != "rule":
                continue
            assert s.condition is not None
            for c in cust.cases:
                if c.case_type == s.signal_id:
                    assert holds(c.record, s.condition)


def test_customers_are_different_enough():
    b, f = _customers()
    assert audit.difference_audit(b, f) == []


def test_every_signal_has_evidence_in_a_nonrecord_source_or_records():
    for cust in _customers():
        chunk_sources = {ch.source_id for ch in cust.chunks}
        manifest = {e.source_id for e in cust.manifest}
        for s in cust.signals:
            locs = [loc for loc in s.locations if loc != "customer_contact"]
            assert locs, s.signal_id
            for loc in locs:
                assert loc in manifest, (s.signal_id, loc)
                if loc not in ("case_records", "txn_records"):
                    assert loc in chunk_sources, (s.signal_id, loc)


# Hand-written records with expected (type, label), independent of the generator.
def _bank(**kw):
    rec = {"alert": {"alert_type": "large_txn"},
           "txn": {"amount_usd": 500.0, "agg30_amt_usd": 600.0, "cp_risk_rating": "standard",
                   "purpose_code": "GDS", "payee_age_days": 100},
           "account": {"account_type": "retail", "age_months": 10, "kyc_status": "complete",
                       "dormant_days": 0, "prior_corridor_count": 0}}
    for k, v in kw.items():
        a, b = k.split("__")
        rec[a][b] = v
    return rec


def test_bank_truth_table_fixed_examples():
    cases = [
        (_bank(), ("base.close", "close_false_positive")),
        (_bank(account__kyc_status="incomplete", txn__amount_usd=50000.0),
         ("base.kyc", "request_info")),
        (_bank(account__dormant_days=200, txn__amount_usd=6000.0),
         ("shared.dormant_reactivation", "escalate")),
        (_bank(alert__alert_type="structuring", txn__purpose_code="PAYR",
               account__account_type="corporate"),
         ("bank.payroll_batches", "close_false_positive")),
        (_bank(txn__cp_risk_rating="high", account__age_months=30,
               account__prior_corridor_count=4),
         ("bank.established_corridor", "close_false_positive")),
        # rolling_30d outranks new_payee when both hold.
        (_bank(txn__amount_usd=4000.0, txn__agg30_amt_usd=12000.0, txn__payee_age_days=3),
         ("bank.rolling_30d", "escalate")),
        (_bank(txn__amount_usd=4000.0, txn__payee_age_days=3), ("bank.new_payee", "request_info")),
        (_bank(txn__payee_age_days=3, txn__amount_usd=2999.0), ("base.close", "close_false_positive")),
        (_bank(txn__amount_usd=10000.0), ("base.large", "escalate")),
    ]
    for rec, expected in cases:
        assert bank.classify(rec) == expected, rec


def test_naive_base_matches_the_base_harness_thresholds():
    # The base harness says $10,000; naive_base must use the same line.
    assert audit.naive_base("bank", _bank(txn__amount_usd=10000.0)) == "escalate"
    assert audit.naive_base("bank", _bank(txn__amount_usd=9999.0)) == "close_false_positive"


def test_new_payee_key_matches_its_evidence():
    s = next(x for x in bank.SIGNALS if x.signal_id == "bank.new_payee")
    assert s.condition is not None
    by_path = {c.path: c.value for c in s.condition.all_of}
    assert by_path == {"txn.payee_age_days": 7, "txn.amount_usd": 3000}


def test_evidence_text_mentions_each_textual_signal():
    b, f = _customers()
    needles = {
        ("bank", "bank.payroll_batches"): ("interview_senior_analyst", "PAYR"),
        ("bank", "shared.dormant_reactivation"): ("interview_ops_lead", "asleep"),
        ("bank", "bank.rolling_30d"): ("interview_ops_lead", "30-day"),
        ("bank", "bank.new_payee"): ("qc_sheet", "Payee was only added"),
        ("bank", "bank.established_corridor"): ("qc_sheet", "corridor"),
        ("fintech", "fintech.crypto_policy_change"): ("slack_ops", "Aug 15"),
        ("fintech", "fintech.home_code"): ("slack_ops", "Home"),
        ("fintech", "shared.dormant_reactivation"): ("slack_ops", "wake-ups"),
        ("fintech", "fintech.rsk_ovr_7"): ("slack_ops", "ovr 7"),
        ("fintech", "fintech.crypto_sop"): ("sop", "Crypto on-ramp"),
    }
    by = {"bank": b, "fintech": f}
    for (cust, sid), (src, needle) in needles.items():
        texts = [c.text for c in by[cust].chunks if c.source_id == src]
        assert any(needle in t for t in texts), (cust, sid, src, needle)


def test_fintech_generation_is_deterministic_including_labels_and_qc():
    f1, f2 = fintech.build(), fintech.build()
    assert [c.record for c in f1.cases] == [c.record for c in f2.cases]
    assert f1.history_labels == f2.history_labels
    b1, b2 = bank.build(), bank.build()
    assert [c.text for c in b1.chunks] == [c.text for c in b2.chunks]
