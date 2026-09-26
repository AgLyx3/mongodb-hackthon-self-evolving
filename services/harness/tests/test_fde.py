from harness.core.conditions import Clause, Condition
from harness.core.fde import KeySignal, decide, judge_unit
from harness.core.kernel import Change, Proposal
from harness.core.units import Unit

RECORDS = [{"a": {"x": x, "y": y}} for x in range(10) for y in range(3)]
SIG = KeySignal(
    signal_id="s1", kind="rule",
    condition=Condition(all_of=(Clause(path="a.x", op=">=", value=5),
                                Clause(path="a.y", op="==", value=1))),
    disposition="escalate", field=None, meaning_keywords=(), description="d")
DEF = KeySignal(signal_id="d1", kind="definition", condition=None, disposition=None,
                field="a.y", meaning_keywords=("home",), description="y=1 means home")


def _rule(*clauses, disp="escalate"):
    return Unit(unit_id="c.r", kind="rule", layer="truth", title="t", text="t",
                applies_when=Condition(all_of=tuple(Clause(path=p, op=o, value=v)
                                                    for p, o, v in clauses)),
                disposition=disp, origin="proposal")


def test_equivalent_scope_different_wording_is_accepted():
    u = _rule(("a.y", "==", 1), ("a.x", ">", 4))  # same extension as x>=5 & y==1
    assert judge_unit(u, [SIG], RECORDS).action == "accept"


def test_too_broad_is_narrowed_to_the_signal():
    j = judge_unit(_rule(("a.x", ">=", 5)), [SIG], RECORDS)
    assert (j.action, j.reason) == ("edit", "too_broad")
    assert j.final_unit is not None and j.final_unit.applies_when == SIG.condition


def test_too_narrow_is_widened():
    j = judge_unit(_rule(("a.x", ">=", 8), ("a.y", "==", 1)), [SIG], RECORDS)
    assert (j.action, j.reason) == ("edit", "too_narrow")


def test_wrong_disposition_is_rejected():
    j = judge_unit(_rule(("a.x", ">=", 5), ("a.y", "==", 1), disp="request_info"), [SIG],
                   RECORDS)
    assert (j.action, j.reason) == ("reject", "wrong")


def test_unrelated_pattern_is_rejected_not_invented():
    j = judge_unit(_rule(("a.x", "<", 2), ("a.y", "==", 0)), [SIG], RECORDS)
    assert j.action == "reject" and j.final_unit is None


def test_definitions():
    good = Unit(unit_id="c.d", kind="definition", layer="truth", title="y",
                text="1 is the Home code", field="a.y", origin="proposal")
    bad = good.model_copy(update={"text": "1 is high risk"})
    other = good.model_copy(update={"field": "a.x"})
    assert judge_unit(good, [DEF], RECORDS).action == "accept"
    assert judge_unit(bad, [DEF], RECORDS).action == "edit"
    assert judge_unit(other, [DEF], RECORDS).action == "reject"


def test_duplicate_of_live_rule_is_rejected():
    live = [_rule(("a.x", ">=", 5), ("a.y", "==", 1))]
    p = Proposal(proposal_id="p", customer="c", batch=1, parent_version="v",
                 change=Change(add=_rule(("a.y", "==", 1), ("a.x", ">", 4))),
                 hypothesis="h", falsification_criterion="f")
    d, _ = decide(p, live, [SIG], RECORDS)
    assert (d.action, d.reason_tag) == ("reject", "duplicate")
