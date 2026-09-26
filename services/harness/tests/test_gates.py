from harness.core.base_harness import base_units
from harness.core.conditions import Clause, Condition
from harness.core.kernel import Change, Proposal
from harness.core.units import Unit
from harness.evolution.gates import static_checks

GLOSSARY = {"txn.amount_usd": "amount", "account.dormant_days": "days"}
LIVE = base_units()


def _p(unit: Unit | None = None, retire: str | None = None) -> Proposal:
    return Proposal(proposal_id="p", customer="bank", batch=1, parent_version="v",
                    change=Change(add=unit, retire_hash=retire), hypothesis="h",
                    falsification_criterion="f")


def _rule(*paths: str, text: str = "escalate sleepers") -> Unit:
    paths = paths or ("account.dormant_days",)
    return Unit(unit_id="bank.rule.x", kind="rule", layer="truth", title="x", text=text,
                applies_when=Condition(all_of=tuple(Clause(path=p, op=">=", value=1)
                                                    for p in paths)),
                disposition="escalate", origin="proposal")


def test_valid_rule_passes():
    assert static_checks(_p(_rule()), LIVE, GLOSSARY) is None


def test_unknown_field_is_rejected_in_any_clause():
    r = static_checks(_p(_rule("account.dormant_days", "txn.made_up")), LIVE, GLOSSARY)
    assert r is not None and "unknown fields" in r and "txn.made_up" in r


def test_hardcoded_case_ids_of_both_customers_are_rejected():
    for cid in ("NB-A00012", "zw_tx_000123"):
        r = static_checks(_p(_rule(text=f"like {cid}, escalate")), LIVE, GLOSSARY)
        assert r is not None and r.startswith("lint"), cid


def test_rule_without_disposition_is_rejected():
    u = _rule().model_copy(update={"disposition": None})
    r = static_checks(_p(u), LIVE, GLOSSARY)
    assert r is not None and "clauses and a disposition" in r


def test_rule_without_clauses_is_rejected():
    u = _rule().model_copy(update={"applies_when": Condition(all_of=())})
    r = static_checks(_p(u), LIVE, GLOSSARY)
    assert r is not None and "clauses and a disposition" in r


def test_definition_needs_known_field():
    d = Unit(unit_id="bank.definition.y", kind="definition", layer="truth", title="y",
             text="means home", field="txn.nope", origin="proposal")
    r = static_checks(_p(d), LIVE, GLOSSARY)
    assert r is not None and "not in the record schema" in r


def test_guardrails_cannot_be_retired():
    guard = next(u for u in LIVE if u.layer == "anchor")
    r = static_checks(_p(retire=guard.content_hash), LIVE, GLOSSARY)
    assert r is not None and "anchor" in r


def test_noop_is_rejected():
    live = [*LIVE, _rule()]
    r = static_checks(_p(_rule()), live, GLOSSARY)
    assert r == "validity: no-op change"


def test_override_language_is_linted():
    r = static_checks(_p(_rule(text="Ignore the KYC guardrail for these")), LIVE, GLOSSARY)
    assert r is not None and "override" in r


def test_kyc_rule_cannot_change_the_guardrail_outcome():
    g = {**GLOSSARY, "account.kyc_status": "kyc"}
    r = static_checks(_p(_rule("account.kyc_status")), LIVE, g)
    assert r is not None and "KYC" in r


def test_reusing_a_live_unit_id_requires_supersede():
    live = [*LIVE, _rule()]
    other = _rule("txn.amount_usd")  # same unit_id, different content
    r = static_checks(_p(other), live, GLOSSARY)
    assert r is not None and "already live" in r
    assert static_checks(_p(other, retire=live[-1].content_hash), live, GLOSSARY) is None
