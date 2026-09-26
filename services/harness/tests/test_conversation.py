"""Conversation ordering (core/conversation.py): pure, from recorded docs only."""

from typing import Any

from harness.core.conversation import build

UNIT = {"kind": "rule", "title": "Sleeper escalation", "text": "Escalate sleepers.",
        "disposition": "escalate",
        "applies_when": {"all_of": [{"path": "account.dormant_days", "op": ">=", "value": 180}]}}


def _docs() -> dict[str, Any]:
    return {
        "probes": [
            {"batch": 1, "run_tag": "main", "tool": "field_stats", "args": {"path": "a"},
             "sources": ["case_records"], "cost": 1, "preview": "stats"},
            {"batch": 1, "run_tag": "main", "tool": "ask_customer", "args": {"question": "q"},
             "sources": ["customer_contact"], "cost": 3, "preview": "answer"},
            {"batch": 1, "run_tag": "ablation_no_priors", "tool": "field_stats",
             "args": {}, "sources": [], "cost": 1, "preview": "ablation"},
        ],
        "findings": [{"batch": 1, "run_tag": "main", "kind": "rule", "statement": "sleepers",
                   "evidence": "qc", "sources": ["qc_sheet"]}],
        "proposals": [
            {"_id": "p1", "batch": 1, "change": {"add": UNIT}, "hypothesis": "h",
             "falsification_criterion": "f", "evidence_refs": ["qc_sheet"]},
            {"_id": "p1r", "batch": 1, "revision_of": "p1", "change": {"add": UNIT}},
            {"_id": "p2", "batch": 1, "change": {"add": UNIT}},
        ],
        "gates": {"p1": [{"gate": "static", "passed": True, "detail": "ok"},
                      {"gate": "summary", "passed": False, "detail": "x"}],
               "p1r": [{"gate": "backtest", "passed": True, "detail": "fixed 3"}],
               "p2": [{"gate": "backtest", "passed": False, "detail": "broke 2"}]},
        "decisions": {
            "p1": {"action": "reject", "fde_id": "sim-fde:jordan", "reason_tag": "overbroad",
                   "rationale": "too broad", "counterexamples": ["c9"]},
            "p1r": {"action": "accept", "fde_id": "sim-fde:jordan", "reason_tag": "correct",
                    "rationale": "ok", "promoted": True, "version": "v2"},
        },
        "feedback": [{"batch": 1, "phase": "start", "fde_id": "sim-fde:jordan", "failed_cases": 4,
                   "explained_cases": 2, "items": [
                       {"message": "ask the ops lead", "n_cases": 2, "cases": ["c1", "c2"]}]},
                  {"batch": 1, "phase": "final", "fde_id": "sim-fde:jordan", "failed_cases": 1,
                   "explained_cases": 0, "items": []}],
        "lessons": [{"lesson_id": "L1", "created_batch": 1, "status": "active", "cause": "not_asked",
                  "text": "Ask the customer."}],
        "reports": [{"batch": 0, "report_acc": 0.4, "version": "v1"},
                 {"batch": 1, "report_acc": 0.6, "version": "v2"}],
        "labels": {"c9": "close_false_positive"},
    }


def test_order_follows_the_loop() -> None:
    msgs = build(**_docs())
    got = [(m.round, m.actor, m.kind, m.ref if m.kind in ("proposal", "revision") else None)
           for m in msgs]
    assert got == [
        (0, "system", "round_start", None),
        (0, "system", "round_result", None),
        (1, "system", "round_start", None),
        (1, "fde", "retro", None),
        (1, "playbook", "lesson", None),
        (1, "investigator", "tool_call", None),
        (1, "tool", "tool_result", None),
        (1, "investigator", "tool_call", None),
        (1, "customer", "tool_result", None),
        (1, "investigator", "finding", None),
        (1, "proposer", "proposal", "p1"),
        (1, "gates", "gate", None),
        (1, "fde", "decision", None),
        (1, "proposer", "revision", "p1r"),
        (1, "gates", "gate", None),
        (1, "fde", "decision", None),
        (1, "system", "promotion", None),
        (1, "proposer", "proposal", "p2"),
        (1, "gates", "gate", None),
        (1, "system", "no_decision", None),
        (1, "system", "round_result", None),
        (1, "fde", "retro", None),
    ]
    assert [m.seq for m in msgs] == list(range(len(msgs)))


def test_content_is_the_recorded_content() -> None:
    msgs = build(**_docs())
    assert all("ablation" not in m.text for m in msgs)
    reject = next(m for m in msgs if m.kind == "decision" and m.ref == "p1")
    assert reject.items == ["c9 (correct: close_false_positive)"]
    assert reject.who == "sim-fde:jordan" and reject.detail == "too broad"
    revision = next(m for m in msgs if m.kind == "revision")
    assert revision.depth == 1
    assert next(m for m in msgs if m.kind == "promotion").ref == "v2"
    assert "account.dormant_days >= 180 → escalate" in msgs[10].items[0]
    assert next(m for m in msgs if m.kind == "retro").items == ["ask the ops lead (2 case(s): c1, c2)"]


def test_auto_accept_is_attributed_to_gates_not_the_fde() -> None:
    d = _docs()
    d["decisions"] = {"p2": {"action": "accept", "fde_id": "auto:gates", "reason_tag": "correct",
                             "rationale": "Auto-accepted", "promoted": False}}
    dec = next(m for m in build(**d) if m.kind == "decision")
    assert dec.actor == "gates" and dec.who == "auto:gates"
