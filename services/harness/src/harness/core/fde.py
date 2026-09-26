"""Simulated FDE: a reactive checker with the answer key (decision 4). Pure, deterministic.

It only reacts to what is proposed:
- rule: compare the proposal's condition to planted signals by *extension*
  (the set of cases it matches), so wording doesn't matter.
    equal extension + same disposition -> accept
    superset / subset / heavy overlap   -> edit to the signal's scope (too_broad /
                                           too_narrow / wrong scope)
    otherwise                           -> reject
- definition: same field and a correct meaning -> accept; right field but
  incomplete meaning -> edit; else reject.
- retire: accept only if the retired unit is itself not supported by the key.
It never adds knowledge that nobody proposed. Rationale text comes from a
persona template.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from harness.core.conditions import Condition, holds
from harness.core.kernel import FdeDecision, Proposal, ReasonTag, unit_edit_distance
from harness.core.units import Unit

PERSONA = "Jordan (FDE, 6 yrs AML deployments)"
FDE_ID = "sim-fde:jordan"


@dataclass(frozen=True)
class KeySignal:
    signal_id: str
    kind: str
    condition: Condition | None
    disposition: str | None
    field: str | None
    meaning_keywords: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class Judgment:
    action: str
    reason: ReasonTag
    signal_id: str | None
    final_unit: Unit | None
    note: str


def _ext(cond: Condition, records: list[dict[str, Any]]) -> frozenset[int]:
    return frozenset(i for i, r in enumerate(records) if holds(r, cond))


def judge_unit(unit: Unit, key: list[KeySignal], records: list[dict[str, Any]]) -> Judgment:
    if unit.kind == "definition":
        return _judge_definition(unit, key)
    if unit.applies_when is None or unit.disposition is None:
        return Judgment("reject", "unsupported", None, None, "rule without scope or outcome")
    prop = _ext(unit.applies_when, records)
    if not prop:
        return Judgment("reject", "unsupported", None, None, "matches no case at all")
    best: tuple[float, KeySignal, frozenset[int]] | None = None
    for s in key:
        if s.kind != "rule" or s.condition is None:
            continue
        sig = _ext(s.condition, records)
        jac = len(prop & sig) / len(prop | sig) if prop | sig else 0.0
        if best is None or jac > best[0]:
            best = (jac, s, sig)
    if best is None or best[0] == 0.0:
        return Judgment("reject", "unsupported", None, None, "no evidence for this pattern")
    jac, s, sig = best
    if unit.disposition != s.disposition:
        return Judgment("reject", "wrong", s.signal_id, None,
                        f"pattern is real but the outcome should be {s.disposition}")
    if prop == sig:
        return Judgment("accept", "correct", s.signal_id, None, "scope and outcome match")
    fixed = unit.model_copy(update={"applies_when": s.condition})
    if prop > sig:
        return Judgment("edit", "too_broad", s.signal_id, fixed, "right idea, too broad")
    if prop < sig:
        return Judgment("edit", "too_narrow", s.signal_id, fixed, "right idea, too narrow")
    if jac >= 0.5:
        return Judgment("edit", "wrong", s.signal_id, fixed, "right idea, scope is off")
    return Judgment("reject", "unsupported", None, None, "overlaps a real pattern only weakly")


def _judge_definition(unit: Unit, key: list[KeySignal]) -> Judgment:
    text = f"{unit.title} {unit.text}".lower()
    for s in key:
        if s.kind != "definition" or s.field != unit.field:
            continue
        if any(k in text for k in s.meaning_keywords):
            return Judgment("accept", "correct", s.signal_id, None, "definition is right")
        fixed = unit.model_copy(update={"text": s.description})
        return Judgment("edit", "wrong", s.signal_id, fixed, "right field, wrong meaning")
    return Judgment("reject", "unsupported", None, None, "not a definition we can confirm")


def decide(proposal: Proposal, live: list[Unit], key: list[KeySignal],
           records: list[dict[str, Any]]) -> tuple[FdeDecision, str | None]:
    """Return the FDE decision and the matched signal id (None if unmatched)."""
    ch = proposal.change
    target = (next((u for u in live if u.content_hash == ch.retire_hash), None)
              if ch.retire_hash else None)
    if ch.retire_hash is not None and (target is None or target.origin == "base"):
        j = Judgment("reject", "unsafe", None, None, "won't retire base policy")
    elif ch.add is not None:
        j = judge_unit(ch.add, key, records)
        if target is not None and j.action in ("accept", "edit"):
            tj = judge_unit(target, key, records)
            # Superseding is fine when it refines the same signal; replacing a correct
            # rule for a different signal would silently delete known truth.
            if tj.action == "accept" and tj.signal_id != j.signal_id:
                j = Judgment("reject", "wrong", tj.signal_id, None,
                             "that would remove a rule we know is right")
        # A duplicate of a signal already covered by a live unit is rejected.
        if j.action in ("accept", "edit") and j.signal_id is not None:
            for u in live:
                if u.origin != "base" and ch.retire_hash != u.content_hash:
                    uj = judge_unit(u, key, records)
                    if uj.signal_id == j.signal_id and uj.action == "accept":
                        j = Judgment("reject", "duplicate", j.signal_id, None,
                                     "already covered by a live rule")
                        break
    else:
        assert target is not None
        if True:
            tj = judge_unit(target, key, records)
            j = (Judgment("accept", "correct", None, None, "agree, that rule was wrong")
                 if tj.action != "accept"
                 else Judgment("reject", "wrong", tj.signal_id, None, "that rule is right"))
    dist = unit_edit_distance(ch.add, j.final_unit) if j.action == "edit" else 0.0
    return FdeDecision(
        proposal_id=proposal.proposal_id, fde_id=FDE_ID, action=j.action,  # type: ignore[arg-type]
        reason_tag=j.reason, rationale=_voice(j), final_unit=j.final_unit,
        edit_distance=dist if j.action == "edit" else (0.0 if j.action == "accept" else 1.0),
    ), j.signal_id


def _voice(j: Judgment) -> str:
    lead = {"accept": "Approved.", "edit": "Approving with an edit.", "reject": "Rejecting."}
    return f"{lead.get(j.action, '')} {j.note[0].upper()}{j.note[1:]}. ({PERSONA})"
