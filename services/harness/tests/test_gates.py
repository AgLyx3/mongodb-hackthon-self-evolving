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


def _rule(path: str = "account.dormant_days", text: str = "escalate sleepers") -> Unit:
    return Unit(unit_id="bank.rule.x", kind="rule", layer="truth", title="x", text=text,
                applies_when=Condition(all_of=(Clause(path=path, op=">=", value=180),)),
                disposition="escalate", origin="proposal")


def test_valid_rule_passes():
    assert static_checks(_p(_rule()), LIVE, GLOSSARY) is None


def test_unknown_field_is_rejected():
    assert "unknown fields" in (static_checks(_p(_rule("txn.made_up")), LIVE, GLOSSARY) or "")


def test_hardcoded_case_id_is_rejected():
    reason = static_checks(_p(_rule(text="like NB-A00012, escalate")), LIVE, GLOSSARY)
    assert reason is not None and reason.startswith("lint")


def test_rule_without_disposition_is_rejected():
    u = _rule().model_copy(update={"disposition": None})
    assert static_checks(_p(u), LIVE, GLOSSARY) is not None


def test_definition_needs_known_field():
    d = Unit(unit_id="bank.definition.y", kind="definition", layer="truth", title="y",
             text="means home", field="txn.nope", origin="proposal")
    assert static_checks(_p(d), LIVE, GLOSSARY) is not None


def test_guardrails_cannot_be_retired():
    guard = next(u for u in LIVE if u.layer == "anchor")
    assert static_checks(_p(retire=guard.content_hash), LIVE, GLOSSARY) is not None


def test_noop_is_rejected():
    base = next(u for u in LIVE if u.layer == "truth")
    assert static_checks(_p(base), LIVE, GLOSSARY) is not None
