"""Kernel: proposals, FDE decisions, promotion. Pure domain code, no I/O.

Invariants (RESEARCH.md §5.9, .claude/rules/harness-evolution.md):
- The proposer only creates `Proposal`s. Only `promote()` builds a new version,
  and it requires an FDE decision of accept or edit.
- Versions are immutable and content-hashed; a no-op change is rejected.
- Anchor-layer units can never be added or retired by a proposal.
"""

from __future__ import annotations

import difflib
from typing import Literal

from pydantic import BaseModel

from harness.core.units import HarnessVersion, NoOpChange, Unit, apply_change, make_version

FdeAction = Literal["accept", "edit", "reject", "defer"]
ReasonTag = Literal["correct", "too_broad", "too_narrow", "wrong", "unsupported",
                    "duplicate", "preference", "unsafe"]


class Change(BaseModel, frozen=True):
    add: Unit | None = None
    retire_hash: str | None = None  # content hash of a live unit to remove/supersede


class Proposal(BaseModel, frozen=True):
    proposal_id: str
    customer: str
    batch: int
    parent_version: str
    change: Change
    hypothesis: str
    falsification_criterion: str
    predicted_fixes: tuple[str, ...] = ()
    risk_cases: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    recalled_proposals: tuple[str, ...] = ()


class FdeDecision(BaseModel, frozen=True):
    proposal_id: str
    fde_id: str  # who signed it; every screen shows who approved what
    action: FdeAction
    reason_tag: ReasonTag
    rationale: str
    final_unit: Unit | None = None  # for edit: what the FDE actually approved
    edit_distance: float = 0.0  # 0 = accepted as-is, ~1 = rewritten


class KernelError(Exception):
    pass


def check_revert(customer: str, target: HarnessVersion) -> None:
    """An FDE revert may only point a customer's pointer at that customer's version."""
    if target.customer != customer:
        raise KernelError("cannot revert to another customer's version")


def unit_edit_distance(proposed: Unit | None, final: Unit | None) -> float:
    if proposed is None or final is None:
        return 0.0 if proposed == final else 1.0
    a, b = _unit_text(proposed), _unit_text(final)
    return round(1.0 - difflib.SequenceMatcher(None, a, b).ratio(), 3)


def _unit_text(u: Unit) -> str:
    cond = u.applies_when.render() if u.applies_when else ""
    return f"{u.title}\n{cond}\n{u.disposition}\n{u.field}\n{u.text}"


def validate_proposal(p: Proposal, current: list[Unit]) -> None:
    """Structural checks the kernel enforces before anything else runs."""
    by_hash = {u.content_hash: u for u in current}
    if p.change.add is None and p.change.retire_hash is None:
        raise KernelError("empty change")
    if p.change.add is not None and p.change.add.layer == "anchor":
        raise KernelError("proposals may not add anchor-layer units")
    if p.change.retire_hash is not None:
        target = by_hash.get(p.change.retire_hash)
        if target is None:
            raise KernelError("retire target is not live")
        if target.layer == "anchor":
            raise KernelError("proposals may not retire anchor-layer units")
        if target.origin == "base":
            raise KernelError("proposals may not retire or supersede base-policy units")


def promote(
    proposal: Proposal,
    decision: FdeDecision,
    current_units: list[Unit],
    current_version: HarnessVersion,
) -> tuple[list[Unit], HarnessVersion]:
    """The only path to a new live version. Requires accept or edit."""
    if decision.proposal_id != proposal.proposal_id:
        raise KernelError("decision is for a different proposal")
    if not decision.fde_id.strip():
        raise KernelError("decision has no signing FDE")
    if decision.action not in ("accept", "edit"):
        raise KernelError(f"cannot promote on FDE action {decision.action!r}")
    if proposal.parent_version != current_version.version_hash:
        raise KernelError("proposal was made against a stale version")
    validate_proposal(proposal, current_units)

    add = proposal.change.add
    if decision.action == "edit":
        if decision.final_unit is None:
            raise KernelError("edit decision without a final unit")
        add = decision.final_unit.model_copy(update={"origin": "fde_edit"})
    if add is not None and add.layer == "anchor":
        raise KernelError("anchor-layer units are FDE-owned, not promotable via proposals")

    try:
        units = apply_change(current_units, add, proposal.change.retire_hash)
    except NoOpChange as e:
        raise KernelError(str(e)) from e
    if add is None:
        edge = "retires"
    elif proposal.change.retire_hash is not None:
        edge = "supersedes"
    else:
        edge = "extends"
    version = make_version(proposal.customer, units, current_version, edge,  # type: ignore[arg-type]
                           proposal.proposal_id)
    return units, version
