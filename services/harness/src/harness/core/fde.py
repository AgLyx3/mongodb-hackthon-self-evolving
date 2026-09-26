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

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Optional, per customer (authored by the eval author): judges the FORM of a
# proposal only, never domain facts. Returns (ok, reason_tag, note).
PresentationCheck = Callable[[dict[str, Any]], tuple[bool, str, str]]

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


def presentation_view(proposal: Proposal) -> dict[str, Any]:
    u = proposal.change.add
    return {"hypothesis": proposal.hypothesis,
            "falsification_criterion": proposal.falsification_criterion,
            "evidence_refs": list(proposal.evidence_refs),
            "unit_text": f"{u.title}. {u.text}" if u else ""}


Visible = list[tuple[str, dict[str, Any], str]]  # (case_id, record, label) the agent has seen

HINTS = {
    "too_broad": "Too broad: your rule also catches cases that should get a different outcome",
    "too_narrow": "Too narrow: it misses cases that belong to the same pattern",
    "wrong": "The scope is off: it catches some wrong cases and misses some right ones",
}


def _counterexamples(unit: Unit, target: Unit, reason: str, visible: Visible) -> tuple[str, ...]:
    """Up to 2 revealed cases the proposal gets wrong. Chosen by the FDE's knowledge,
    but only case ids are returned: the agent must work out why."""
    if unit.applies_when is None or target.applies_when is None:
        return ()
    out: list[str] = []
    for cid, rec, label in sorted(visible, key=lambda v: v[0]):
        in_p, in_s = holds(rec, unit.applies_when), holds(rec, target.applies_when)
        if reason in ("too_broad", "wrong") and in_p and not in_s and label != unit.disposition:
            out.append(cid)
        elif reason in ("too_narrow", "wrong") and in_s and not in_p and label == unit.disposition:
            out.append(cid)
        if len(out) == 2:
            break
    return tuple(out)


def _noise_draw(proposal: Proposal, seed: int) -> float:
    import hashlib

    u = proposal.change.add
    basis = f"{seed}:{u.content_hash if u else proposal.change.retire_hash}"
    return int(hashlib.sha256(basis.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def decide(proposal: Proposal, live: list[Unit], key: list[KeySignal],
           records: list[dict[str, Any]],
           presentation_check: PresentationCheck | None = None,
           *, mode: str = "hints", visible: Visible | None = None, allow_revise: bool = True,
           noise: float = 0.0, seed: int = 0,
           ) -> tuple[FdeDecision, str | None]:
    """Return the FDE decision and the matched signal id (None if unmatched).

    mode "oracle": edits too-broad/narrow rules to the exact answer-key scope.
    mode "hints": never supplies scope; returns "revise" + counterexample case ids
      (or "reject" when no revision is allowed).
    noise: seeded probability of flipping the verdict (accept<->reject), to model a
      fallible reviewer; flips are marked in the rationale only as "Not convinced."
    """
    fd, sig = _decide_hinted(proposal, live, key, records, mode, visible or [], allow_revise)
    if presentation_check is not None and fd.action in ("accept", "edit", "revise"):
        ok, tag, note = presentation_check(presentation_view(proposal))
        if not ok:
            j = Judgment("reject", "presentation", sig, None,
                         f"content aside, the write-up isn't usable ({tag}): {note}")
            fd = FdeDecision(proposal_id=proposal.proposal_id, fde_id=FDE_ID,
                             action="revise" if allow_revise else "reject",
                             reason_tag="presentation", rationale=_voice(j), edit_distance=1.0)
    if noise > 0 and _noise_draw(proposal, seed) < noise and proposal.change.add is not None:
        if fd.action in ("accept", "edit"):
            fd = fd.model_copy(update={"action": "reject", "reason_tag": "preference",
                                       "final_unit": None, "edit_distance": 1.0,
                                       "counterexamples": (),
                                       "rationale": f"Rejecting. Not convinced. ({PERSONA})"})
        elif fd.action in ("reject", "revise") and fd.reason_tag not in ("unsafe", "duplicate"):
            fd = fd.model_copy(update={"action": "accept", "reason_tag": "preference",
                                       "final_unit": None, "edit_distance": 0.0,
                                       "counterexamples": (),
                                       "rationale": f"Approved. Looks fine to me. ({PERSONA})"})
    return fd, sig


def _decide_hinted(proposal: Proposal, live: list[Unit], key: list[KeySignal],
                   records: list[dict[str, Any]], mode: str, visible: Visible,
                   allow_revise: bool) -> tuple[FdeDecision, str | None]:
    fd, sig = _decide_with_presentation(proposal, live, key, records, None)
    if mode != "hints" or fd.action != "edit":
        return fd, sig
    unit, target = proposal.change.add, fd.final_unit
    assert unit is not None and target is not None
    ce = _counterexamples(unit, target, fd.reason_tag, visible) if unit.kind == "rule" else ()
    hint = (HINTS.get(fd.reason_tag, "Not quite right") if unit.kind == "rule"
            else "The meaning you gave this field doesn't match how the customer uses it")
    cases = f" See {', '.join(ce)}." if ce else " Check the customer's own explanation."
    action = "revise" if allow_revise else "reject"
    lead = "Send it back." if allow_revise else "Rejecting."
    return FdeDecision(proposal_id=proposal.proposal_id, fde_id=FDE_ID, action=action,  # type: ignore[arg-type]
                       reason_tag=fd.reason_tag, counterexamples=ce, edit_distance=1.0,
                       rationale=f"{lead} {hint}.{cases} ({PERSONA})"), sig


def _decide_with_presentation(proposal: Proposal, live: list[Unit], key: list[KeySignal],
                              records: list[dict[str, Any]],
                              presentation_check: PresentationCheck | None,
                              ) -> tuple[FdeDecision, str | None]:
    return _decide_content(proposal, live, key, records)


def _decide_content(proposal: Proposal, live: list[Unit], key: list[KeySignal],
                    records: list[dict[str, Any]]) -> tuple[FdeDecision, str | None]:
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
