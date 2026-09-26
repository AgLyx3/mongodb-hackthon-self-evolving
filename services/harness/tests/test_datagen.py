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
                 for s in ("batch1", "batch2", "batch3", "holdout")}
        assert sizes == {"batch1": 30, "batch2": 30, "batch3": 30, "holdout": 40}


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
