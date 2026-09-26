"""FDE retrospective (core/fde_retro.py): pure, deterministic, knowledge-bounded."""

import random
import re

from harness.core.conditions import Clause, Condition
from harness.core.fde import KeySignal
from harness.core.fde_retro import (
    FailedCase, FindingRecord, LiveUnit, ProbeRecord, causes_due_for_lesson, lint_lesson,
    retro, stated_support,
)
from harness.core.units import Unit

# Answer-key values chosen so they can't collide with anything the templates print.
RULE = KeySignal(
    signal_id="sig.rule_one", kind="rule",
    condition=Condition(all_of=(Clause(path="a.x", op=">=", value=17),
                                Clause(path="a.y", op="==", value=42))),
    disposition="escalate", field=None, meaning_keywords=(),
    description="secret answer-key description [KEY-deadbeef]",
    locations=("qc_notes", "interview_x"))
CONTACT = KeySignal(
    signal_id="sig.contact_only", kind="rule",
    condition=Condition(all_of=(Clause(path="b.code", op="==", value="zeta"),)),
    disposition="close_false_positive", field=None, meaning_keywords=(),
    description="code zeta is an allowlist [KEY-cafef00d]",
    locations=("recs", "customer_contact"))
KEY = [RULE, CONTACT]
RECORDS = ([{"a": {"x": x, "y": y}, "b": {"code": "none"}}
            for x in range(10, 30) for y in (1, 42)]
           + [{"a": {"x": 1, "y": 1}, "b": {"code": c}} for c in ("zeta", "eta", "none")])
REC_SRC = ("recs",)
IN_RULE = {"a": {"x": 20, "y": 42}, "b": {"code": "none"}}
OUT_RULE = {"a": {"x": 20, "y": 1}, "b": {"code": "none"}}
IN_CONTACT = {"a": {"x": 1, "y": 1}, "b": {"code": "zeta"}}


def _fc(cid, record, label="escalate", applied=(), case_type=None):
    return FailedCase(case_id=cid, record=record, predicted="close_false_positive",
                      label=label, applied=tuple(applied), case_type=case_type)


def _unit(uid, *clauses, disp="escalate"):
    return Unit(unit_id=uid, kind="rule", layer="truth", title="t", text="t",
                applies_when=Condition(all_of=tuple(Clause(path=p, op=o, value=v)
                                                    for p, o, v in clauses)),
                disposition=disp, origin="proposal")


def _run(failed, live=(), probes=(), findings=(), revealed=None):
    return retro(failed=list(failed), live_units=list(live), probes=list(probes),
                 findings=list(findings), key=KEY, records=RECORDS, record_sources=REC_SRC,
                 revealed_case_ids=revealed)


def _only(review):
    assert len(review.items) == 1, review.items
    return review.items[0]


# ------------------------------------------------------------------ one fixture per cause

def test_premature_unit_backed_by_thin_evidence():
    u = _unit("c.rule.hunch", ("a.x", ">=", 25), ("a.y", "==", 1))  # no real pattern
    live = [LiveUnit(unit=u, evidence_text="saw this in 3 cases", created_batch=2)]
    it = _only(_run([_fc("case-a", {"a": {"x": 26, "y": 1}, "b": {"code": "none"}},
                         applied=["c.rule.hunch"])], live))
    assert (it.cause, it.target_unit_id, it.suggested_action) == (
        "premature", "c.rule.hunch", "retire_unit")


def test_overgeneralized_unit_fires_outside_the_signal():
    u = _unit("c.rule.wide", ("a.x", ">=", 17), disp="escalate")
    live = [LiveUnit(unit=u, evidence_text="label_breakdown 40/44 escalated",
                     created_batch=2)]
    it = _only(_run([_fc("case-b", OUT_RULE, label="close_false_positive",
                         applied=["c.rule.wide"])], live))
    assert (it.cause, it.target_unit_id, it.suggested_action) == (
        "overgeneralized", "c.rule.wide", "revise_unit")
    assert "a.x" in it.message  # a field path the agent itself used


def test_partial_data_when_no_evidence_location_was_probed():
    probes = [ProbeRecord("field_stats", ("recs",), {"path": "a.x"})]
    it = _only(_run([_fc("case-c", IN_RULE)], probes=probes))
    assert (it.cause, it.suggested_action) == ("partial_data", "probe_source")
    assert "qc_notes" in it.message and "interview_x" in it.message


def test_missed_in_read_when_probed_but_no_finding():
    probes = [ProbeRecord("read_source", ("qc_notes",), {"source_id": "qc_notes"})]
    it = _only(_run([_fc("case-d", IN_RULE)], probes=probes))
    assert (it.cause, it.suggested_action) == ("missed_in_read", "reread_source")
    assert "qc_notes" in it.message


def test_not_asked_when_only_the_customer_knows():
    it = _only(_run([_fc("case-e", IN_CONTACT, label="close_false_positive")]))
    assert (it.cause, it.suggested_action) == ("not_asked", "ask_customer")
    assert "who at the customer would know about b.code" in it.message.lower()


def test_asking_about_the_field_clears_not_asked():
    probes = [ProbeRecord("ask_customer", ("customer_contact",),
                          {"question": "What does b.code mean?"})]
    it = _only(_run([_fc("case-e", IN_CONTACT, label="close_false_positive")], probes=probes))
    assert it.cause != "not_asked"


def test_conflict_hidden_when_finding_cites_one_of_several_sources():
    probes = [ProbeRecord("read_source", ("qc_notes",), {})]
    f = FindingRecord(kind="rule", statement="big ones escalate", field="",
                      clause_paths=("a.x",), sources=("qc_notes",), evidence="12/14 escalated",
                      batch=1)
    it = _only(_run([_fc("case-f", IN_RULE)], probes=probes, findings=[f]))
    assert (it.cause, it.suggested_action) == ("conflict_hidden", "cross_check_sources")
    assert "qc_notes" in it.message and "a.x" in it.message


def test_format_when_finding_has_no_numbers_or_quotes():
    probes = [ProbeRecord("read_source", ("qc_notes",), {})]
    f = FindingRecord(kind="rule", statement="big ones escalate", field="",
                      clause_paths=("a.x", "a.y"), sources=("qc_notes", "interview_x"),
                      evidence="the reviewers say so", batch=1)
    it = _only(_run([_fc("case-g", IN_RULE)], probes=probes, findings=[f]))
    assert (it.cause, it.suggested_action) == ("format", "cite_evidence")


def test_base_policy_failures_are_not_blamed_on_discovery():
    review = _run([_fc("case-h", IN_RULE, case_type="base.large")])
    assert review.items == () and review.failed == 1


def test_stated_support_parses_agent_counts():
    assert stated_support("12/14 escalated; n=30") == 30
    assert stated_support("9 of 11 cases") == 11 or stated_support("9 of 11 cases") == 9
    assert stated_support("the reviewers say so") is None


# ------------------------------------------------------------------ ranking and bounds

def _mixed():
    wide = _unit("c.rule.wide", ("a.x", ">=", 17))
    hunch = _unit("c.rule.hunch", ("a.x", ">=", 25), ("a.y", "==", 1))
    live = [LiveUnit(unit=wide, evidence_text="40/44", created_batch=2),
            LiveUnit(unit=hunch, evidence_text="3 cases", created_batch=2)]
    failed = ([_fc(f"case-p{c}", IN_RULE) for c in "abcde"]  # partial_data x5
              + [_fc(f"case-n{c}", IN_CONTACT, label="close_false_positive") for c in "ab"]
              + [_fc("case-o", OUT_RULE, label="close_false_positive",
                     applied=["c.rule.wide"])]
              + [_fc("case-q", {"a": {"x": 11, "y": 1}, "b": {"code": "none"}},
                     applied=["c.rule.hunch"])])
    return failed, live


def test_ranked_by_cases_explained_and_capped_at_three():
    failed, live = _mixed()
    review = _run(failed, live)
    assert [i.cause for i in review.items][:2] == ["partial_data", "not_asked"]
    assert [i.n_cases for i in review.items] == [5, 2, 1]
    assert len(review.items) == 3
    assert review.items[2].cause == "premature"  # ties broken by cause order
    assert review.items[0].cases == ("case-pa", "case-pb", "case-pc")  # at most 3 shown


def test_only_revealed_case_ids_are_used():
    failed, live = _mixed()
    revealed = {f.case_id for f in failed} - {"case-pa", "case-na"}
    review = _run(failed, live, revealed=revealed)
    shown = {c for i in review.items for c in i.cases}
    assert shown <= revealed
    assert all("case-pa" not in i.message and "case-na" not in i.message for i in review.items)
    assert review.failed == len(failed) - 2


def test_deterministic_regardless_of_input_order():
    failed, live = _mixed()
    a = _run(failed, live)
    shuffled = failed[:]
    random.Random(7).shuffle(shuffled)
    assert _run(shuffled, list(reversed(live))) == a


# ------------------------------------------------------------------ knowledge boundary

def _all_messages():
    failed, live = _mixed()
    probes_sets = [(), [ProbeRecord("read_source", ("qc_notes",), {})]]
    f1 = FindingRecord("rule", "s", "", ("a.x",), ("qc_notes",), "12/14", 1)
    f2 = FindingRecord("rule", "s", "", ("a.x",), ("qc_notes", "interview_x"), "they say", 1)
    msgs = []
    for probes in probes_sets:
        for findings in ((), [f1], [f2]):
            for i in _run(failed, live, probes, findings).items:
                msgs.append(i.message)
    assert {m.split(" ")[0] for m in msgs}  # sanity: we produced messages
    return msgs


def test_messages_never_leak_the_answer_key():
    values = [str(c.value) for s in KEY for c in s.condition.all_of]
    for m in _all_messages():
        assert "KEY-" not in m
        for s in KEY:
            assert s.signal_id not in m
            assert s.description[:20] not in m
        for v in values:
            assert not re.search(rf"(?<![\w.]){re.escape(v)}(?![\w])", m), (v, m)
        assert "Jordan" in m


# ------------------------------------------------------------------ playbook lessons

def test_lesson_lint():
    assert lint_lesson("Before proposing a rule, always confirm it on the customer's "
                       "outcomes from more than one round.") is None
    assert lint_lesson("Check amounts above 5000 first.") == "contains digits"
    assert lint_lesson('Treat the code "H" as home.') == "contains a quoted string"
    assert lint_lesson("Treat 'H' as home.") == "contains a quoted string"
    assert lint_lesson("Mind KEY-abc") is not None
    assert lint_lesson("  ") == "empty"


def test_causes_due_for_lesson_need_two_items_and_no_active_lesson():
    seen = ["partial_data", "premature", "partial_data", "format", "format"]
    assert causes_due_for_lesson(seen, []) == ["format", "partial_data"]
    assert causes_due_for_lesson(seen, ["format"]) == ["partial_data"]
    assert causes_due_for_lesson(["premature"], []) == []
