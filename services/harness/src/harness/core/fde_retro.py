"""Simulated FDE retrospective on the agent's discovery METHOD. Pure, deterministic.

After a round's outcomes are revealed, the FDE ("Jordan") takes the cases the
live harness got wrong and traces each one backwards through the agent's own
trail: which live unit fired, which planted signal actually decided the case,
where that signal's evidence lives, what the investigator probed, asked and
wrote down. Each failed case gets at most one cause; causes are grouped,
ranked by how many failures they explain, and the top 3 are returned as
templated method feedback.

Knowledge boundary (tested): messages may name a source id, a revealed case id,
a field path the agent already used, or a question category ("who at the
customer would know about <field the record shows>?"). They never contain
answer-key thresholds or values, signal ids, answer-key descriptions, or
canary tokens. The answer key is used only to *choose* what to say.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

from harness.core.conditions import Condition, get_path, holds
from harness.core.fde import FDE_ID, KeySignal
from harness.core.units import Unit

Cause = Literal["premature", "overgeneralized", "partial_data", "missed_in_read",
                "not_asked", "conflict_hidden", "format"]
Action = Literal["retire_unit", "revise_unit", "probe_source", "reread_source",
                 "ask_customer", "cross_check_sources", "cite_evidence"]
CAUSES: tuple[Cause, ...] = ("premature", "overgeneralized", "partial_data", "missed_in_read",
                             "not_asked", "conflict_hidden", "format")
ACTION: dict[Cause, Action] = {
    "premature": "retire_unit", "overgeneralized": "revise_unit",
    "partial_data": "probe_source", "missed_in_read": "reread_source",
    "not_asked": "ask_customer", "conflict_hidden": "cross_check_sources",
    "format": "cite_evidence"}
CUSTOMER_CONTACT = "customer_contact"
MIN_SUPPORT = 5  # a rule resting on fewer stated cases is premature
MIN_SUPPORT_ONE_ROUND = 10  # ...and on fewer than this if it saw one round of outcomes
MAX_ITEMS = 3
MAX_CASES = 3
SIGN = "(Jordan, FDE)"


@dataclass(frozen=True)
class FailedCase:
    case_id: str
    record: dict[str, Any]
    predicted: str | None
    label: str
    applied: tuple[str, ...] = ()
    # Answer-key case type (which signal decided it), if the caller has it.
    case_type: str | None = None


@dataclass(frozen=True)
class LiveUnit:
    """A live agent-proposed unit with its provenance."""
    unit: Unit
    evidence_text: str = ""  # finding evidence + proposal hypothesis the unit rests on
    sources: tuple[str, ...] = ()
    created_batch: int = 0


@dataclass(frozen=True)
class ProbeRecord:
    tool: str
    sources: tuple[str, ...]
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FindingRecord:
    kind: str
    statement: str
    field: str
    clause_paths: tuple[str, ...]
    sources: tuple[str, ...]
    evidence: str
    batch: int = 0


@dataclass(frozen=True)
class RetroItem:
    cause: Cause
    target_unit_id: str | None
    cases: tuple[str, ...]
    message: str
    suggested_action: Action
    n_cases: int = 0  # failed cases this item explains (cases is capped at 3)


@dataclass(frozen=True)
class RetroReview:
    items: tuple[RetroItem, ...]
    fde_id: str = FDE_ID
    failed: int = 0
    explained: int = 0


# ----------------------------------------------------------------------------- helpers

_N_PATTERNS = (re.compile(r"\b(\d+)\s*/\s*(\d+)\b"), re.compile(r"\b(\d+)\s+of\s+(\d+)\b"),
               re.compile(r"\bn\s*=\s*(\d+)\b", re.IGNORECASE),
               re.compile(r"\b(\d+)\s+(?:cases|alerts|reviews|payments|txns?|transactions)\b",
                          re.IGNORECASE))


def stated_support(text: str) -> int | None:
    """Largest case count the agent itself stated (n/N, 'n of N', n=, 'n cases')."""
    best: int | None = None
    for pat in _N_PATTERNS:
        for m in pat.finditer(text):
            n = int(m.group(1))
            best = n if best is None else max(best, n)
    return best


def _paths(u: Unit) -> tuple[str, ...]:
    if u.applies_when is not None:
        return tuple(sorted(u.applies_when.paths()))
    return (u.field,) if u.field else ()


def _signal_paths(s: KeySignal) -> tuple[str, ...]:
    if s.condition is not None:
        return tuple(sorted(s.condition.paths()))
    return (s.field,) if s.field else ()


def _ext(cond: Condition, records: list[dict[str, Any]]) -> frozenset[int]:
    return frozenset(i for i, r in enumerate(records) if holds(r, cond))


def _best_signal(u: Unit, key: list[KeySignal], records: list[dict[str, Any]]
                 ) -> KeySignal | None:
    """The planted rule signal whose extension overlaps the unit's most (Jaccard)."""
    if u.applies_when is None:
        return next((k for k in key if k.kind == "definition"
                     and k.field == u.field), None)
    prop = _ext(u.applies_when, records)
    best: tuple[float, KeySignal] | None = None
    for k in key:
        if k.kind != "rule" or k.condition is None:
            continue
        sig = _ext(k.condition, records)
        union = prop | sig
        jac = len(prop & sig) / len(union) if union else 0.0
        if jac > 0 and (best is None or jac > best[0]):
            best = (jac, k)
    return best[1] if best else None


def _signal_for_case(fc: FailedCase, key: list[KeySignal]) -> KeySignal | None:
    if fc.case_type:
        hit = next((k for k in key if k.signal_id == fc.case_type), None)
        if hit is not None:
            return hit
        if fc.case_type.startswith("base."):
            return None  # decided by base policy: not a discovery miss
    for k in key:
        if k.kind == "rule" and k.condition is not None \
                and holds(fc.record, k.condition):
            return k
    return None


def _mentions(text: str, path: str) -> bool:
    leaf = path.rsplit(".", 1)[-1].lower()
    t = text.lower()
    return path.lower() in t or (len(leaf) >= 3 and leaf in t)


def _covering(findings: list[FindingRecord], sk: KeySignal) -> FindingRecord | None:
    """Latest finding that speaks to the signal's fields."""
    paths = set(_signal_paths(sk))
    hits = [f for f in findings
            if paths & (set(f.clause_paths) | ({f.field} if f.field else set()))
            or (sk.kind == "definition" and any(_mentions(f.statement, p) for p in paths))]
    return max(hits, key=lambda f: f.batch) if hits else None


def _finding_field(f: FindingRecord) -> str:
    return f.field or (f.clause_paths[0] if f.clause_paths else "this pattern")


def has_evidence_format(text: str) -> bool:
    return bool(re.search(r"\d", text)) or bool(re.search(r"[\"“”]", text))


def _cases(ids: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(ids)))[:MAX_CASES]


def _join(xs: Iterable[str]) -> str:
    xs = list(xs)
    return ", ".join(xs[:-1]) + (" and " if len(xs) > 1 else "") + xs[-1] if xs else ""


# ----------------------------------------------------------------------------- tracing

@dataclass(frozen=True)
class _Trace:
    cause: Cause
    group: str  # internal grouping key (may contain answer-key ids; never rendered)
    target_unit_id: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


def _trace_unit(fc: FailedCase, lu: LiveUnit, key: list[KeySignal],
                records: list[dict[str, Any]]) -> _Trace | None:
    u = lu.unit
    sk = _best_signal(u, key, records)
    uid = u.unit_id
    if u.applies_when is not None and sk is not None and sk.condition is not None \
            and not holds(fc.record, sk.condition):
        return _Trace("overgeneralized", f"unit:{uid}", uid, {"paths": _paths(u)})
    n = stated_support(lu.evidence_text)
    need = MIN_SUPPORT_ONE_ROUND if lu.created_batch <= 1 else MIN_SUPPORT
    if sk is None or n is None or n < need:
        return _Trace("premature", f"unit:{uid}", uid, {"n": n, "batch": lu.created_batch})
    return None


def _trace_signal(fc: FailedCase, sk: KeySignal, probes: list[ProbeRecord],
                  findings: list[FindingRecord], record_sources: frozenset[str]) -> _Trace | None:
    sid = sk.signal_id
    probed = {s for p in probes for s in p.sources}
    non_record = tuple(loc for loc in sk.locations if loc not in record_sources)
    fields_in_record = [p for p in _signal_paths(sk) if get_path(fc.record, p) is not None]
    if non_record and set(non_record) == {CUSTOMER_CONTACT}:
        questions = [str(p.args.get("question", "")) for p in probes if p.tool == "ask_customer"]
        if not any(_mentions(q, f) for q in questions for f in _signal_paths(sk)):
            return _Trace("not_asked", f"sig:{sid}", None,
                          {"field": fields_in_record[0] if fields_in_record else None})
    unprobed = tuple(loc for loc in non_record if loc not in probed)
    if non_record and len(unprobed) == len(non_record):
        return _Trace("partial_data", f"sig:{sid}", None, {"sources": unprobed})
    cover = _covering(findings, sk)
    if cover is None:
        seen = tuple(loc for loc in sk.locations if loc in probed)
        return _Trace("missed_in_read", f"sig:{sid}", None, {"sources": seen})
    if len(set(cover.sources)) == 1 and len(sk.locations) >= 2:
        return _Trace("conflict_hidden", f"sig:{sid}", None,
                      {"field": _finding_field(cover), "source": cover.sources[0]})
    if not has_evidence_format(cover.evidence):
        return _Trace("format", f"sig:{sid}", None, {"field": _finding_field(cover)})
    return None


def _message(t: _Trace, cases: tuple[str, ...]) -> str:
    cs = _join(cases)
    d = t.detail
    match t.cause:
        case "premature":
            n = d.get("n")
            support = (f"the evidence you wrote down states only {n} supporting cases"
                       if n is not None else "the evidence you wrote down states no case count")
            return (f"{t.target_unit_id} decided {cs} wrongly, and {support}. Before a rule "
                    f"goes live, confirm it on outcomes from more than one round with "
                    f"label_breakdown and report n/N. Re-test it or retire it. {SIGN}")
        case "overgeneralized":
            return (f"{t.target_unit_id} fired on {cs}, where the right outcome is different. "
                    f"Its scope is wider than the pattern: compare these cases with the ones it "
                    f"got right on {_join(d['paths'])} and narrow it. {SIGN}")
        case "partial_data":
            return (f"I can't see any evidence you read that explains {cs}. You never probed "
                    f"{_join(d['sources'])}. Look at what it says about cases like these "
                    f"before relying on the records alone. {SIGN}")
        case "missed_in_read":
            where = (f"You probed {_join(d['sources'])}" if d["sources"]
                     else "You looked at the records")
            return (f"{where}, but none of your findings explain {cs}. Re-read it with these "
                    f"cases side by side and write down what separates them. {SIGN}")
        case "not_asked":
            fld = d.get("field")
            about = f"about {fld}" if fld else "about what these cases have in common"
            return (f"Nothing you read explains {cs}, and you never asked the customer. Who at "
                    f"the customer would know {about}? Ask them. {SIGN}")
        case "conflict_hidden":
            return (f"Your finding on {d['field']} cites only {d['source']}, and {cs} still "
                    f"fail. Other sources speak to the same cases; cross-check them before "
                    f"concluding, and say which one wins when they disagree. {SIGN}")
        case "format":
            return (f"Your finding on {d['field']} gives no counts and no quotes, so I can't "
                    f"check it against {cs}. State n/N from label_breakdown or quote the "
                    f"source. {SIGN}")
    raise AssertionError(t.cause)


def retro(
    *, failed: list[FailedCase], live_units: list[LiveUnit], probes: list[ProbeRecord],
    findings: list[FindingRecord], key: list[KeySignal], records: list[dict[str, Any]],
    record_sources: Iterable[str] = (), revealed_case_ids: Iterable[str] | None = None,
) -> RetroReview:
    """Map each failed case to at most one cause; return the top 3 grouped items."""
    rec_src = frozenset(record_sources)
    allowed = None if revealed_case_ids is None else set(revealed_case_ids)
    cases = sorted((fc for fc in failed if allowed is None or fc.case_id in allowed),
                   key=lambda fc: fc.case_id)
    agent_units = {lu.unit.unit_id: lu for lu in live_units
                   if lu.unit.origin != "base" and lu.unit.layer != "anchor"}
    groups: dict[tuple[Cause, str], tuple[_Trace, list[str]]] = {}
    for fc in cases:
        trace: _Trace | None = None
        for uid in sorted(set(fc.applied) & set(agent_units)):
            trace = _trace_unit(fc, agent_units[uid], key, records)
            if trace is not None:
                break
        if trace is None:
            sk = _signal_for_case(fc, key)
            if sk is not None:
                trace = _trace_signal(fc, sk, probes, findings, rec_src)
        if trace is None:
            continue
        g = groups.setdefault((trace.cause, trace.group), (trace, []))
        g[1].append(fc.case_id)
    ranked = sorted(groups.values(),
                    key=lambda tc: (-len(tc[1]), CAUSES.index(tc[0].cause), tc[0].group))
    items = []
    for t, ids in ranked[:MAX_ITEMS]:
        cs = _cases(ids)
        items.append(RetroItem(cause=t.cause, target_unit_id=t.target_unit_id, cases=cs,
                               message=_message(t, cs), suggested_action=ACTION[t.cause],
                               n_cases=len(ids)))
    return RetroReview(items=tuple(items), failed=len(cases),
                       explained=sum(len(ids) for _, ids in groups.values()))


# ----------------------------------------------------------------------------- lessons

_QUOTED = re.compile(r"\"[^\"]+\"|“[^”]+”|(?<![A-Za-z])'[^']+'(?![A-Za-z])")


def lint_lesson(text: str) -> str | None:
    """A playbook lesson must be general method advice: no digits (thresholds, counts,
    case ids), no quoted strings (field values), no canary tokens. Returns a reason or None."""
    t = text.strip()
    if not t:
        return "empty"
    if "KEY-" in t:
        return "contains an answer-key canary"
    if re.search(r"\d", t):
        return "contains digits"
    if _QUOTED.search(t):
        return "contains a quoted string"
    return None


def causes_due_for_lesson(item_causes: Iterable[str], active_lesson_causes: Iterable[str],
                          threshold: int = 2) -> list[str]:
    """Causes seen in >= threshold retro items (across rounds) that have no active lesson."""
    counts: dict[str, int] = {}
    for c in item_causes:
        counts[c] = counts.get(c, 0) + 1
    active = set(active_lesson_causes)
    return sorted(c for c, n in counts.items() if n >= threshold and c not in active)


def render_feedback(items: list[dict[str, Any]]) -> str:
    if not items:
        return "(no feedback yet)"
    out = []
    for i, it in enumerate(items, 1):
        tgt = f" target unit: {it['target_unit_id']};" if it.get("target_unit_id") else ""
        out.append(f"{i}. [{it['cause']}]{tgt} suggested: {it['suggested_action']}\n   "
                   f"{it['message']}")
    return "\n".join(out)


def render_playbook(lessons: list[dict[str, Any]]) -> str:
    if not lessons:
        return "(no lessons yet)"
    return "\n".join(f"- {lesson['text']} (learned round {lesson['created_batch']}, "
                     f"from repeated '{lesson['cause']}' feedback)" for lesson in lessons)
