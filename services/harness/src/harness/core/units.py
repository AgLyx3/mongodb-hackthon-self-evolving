"""Harness units and versions (decision 2): the procedural memory.

A version is an immutable set of unit content hashes. Units are immutable too;
editing a unit creates a new unit whose `supersedes` points at the old one.
Pure domain code: hashing, no-op detection, rendering. No I/O.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, Field

from harness.core.conditions import Condition, Disposition

UnitKind = Literal["rule", "definition", "lookup", "skill"]
# truth = portable customer knowledge; binding = model-specific settings;
# anchor = FDE-owned guardrails the proposer may never touch.
Layer = Literal["truth", "binding", "anchor"]
EdgeType = Literal["base", "extends", "repairs", "retires", "supersedes", "reverts"]


class Unit(BaseModel, frozen=True):
    unit_id: str  # stable logical id, e.g. "bank.rule.payroll_batches"
    kind: UnitKind
    layer: Layer
    title: str
    text: str  # prose the runtime agent reads
    applies_when: Condition | None = None
    disposition: Disposition | None = None  # rules only
    field: str | None = None  # definitions only: which record field it explains
    supersedes: str | None = None  # content hash of the unit this replaces
    origin: Literal["base", "proposal", "fde_edit"] = "base"

    @property
    def content_hash(self) -> str:
        payload = self.model_dump(mode="json", exclude={"origin"})
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


class HarnessVersion(BaseModel, frozen=True):
    customer: str
    unit_hashes: tuple[str, ...] = Field(description="sorted content hashes")
    parent: str | None = None
    edge: EdgeType = "base"
    proposal_id: str | None = None

    @property
    def version_hash(self) -> str:
        blob = json.dumps(
            {"customer": self.customer, "units": sorted(self.unit_hashes)}, sort_keys=True
        )
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


def make_version(
    customer: str,
    units: list[Unit],
    parent: HarnessVersion | None,
    edge: EdgeType,
    proposal_id: str | None = None,
) -> HarnessVersion:
    return HarnessVersion(
        customer=customer,
        unit_hashes=tuple(sorted(u.content_hash for u in units)),
        parent=parent.version_hash if parent else None,
        edge=edge,
        proposal_id=proposal_id,
    )


class NoOpChange(Exception):
    """A proposal whose result has the same content hash as its parent."""


def apply_change(
    current: list[Unit], add: Unit | None, retire_hash: str | None
) -> list[Unit]:
    """Return the unit list after adding and/or retiring one unit.

    Raises NoOpChange if nothing changes, so no-op proposals are detectable.
    """
    by_hash = {u.content_hash: u for u in current}
    if retire_hash is not None and retire_hash not in by_hash:
        raise KeyError(f"unit {retire_hash} not in current version")
    new = dict(by_hash)
    if retire_hash is not None:
        del new[retire_hash]
    if add is not None:
        new[add.content_hash] = add
    if set(new) == set(by_hash):
        raise NoOpChange("change produces an identical harness")
    return list(new.values())


def _render_unit(u: Unit) -> list[str]:
    lines = [f"### [{u.unit_id}] {u.title}"]
    if u.field is not None:
        lines.append(f"Field: {u.field}")
    if u.applies_when is not None:
        lines.append(f"Applies when: {u.applies_when.render()}")
    if u.disposition is not None:
        lines.append(f"Disposition: {u.disposition}")
    lines.append(u.text.strip())
    lines.append("")
    return lines


def render_harness(units: list[Unit]) -> str:
    """Render units into the AGENTS.md-style text the runtime agent reads."""
    anchor = sorted((u for u in units if u.layer == "anchor"), key=lambda u: u.unit_id)
    custom = sorted((u for u in units if u.layer != "anchor" and u.origin != "base"),
                    key=lambda u: (u.kind != "definition", u.unit_id))
    base = sorted((u for u in units if u.layer != "anchor" and u.origin == "base"),
                  key=lambda u: u.unit_id)
    lines = ["# Triage harness", "", "## Guardrails (always apply)", ""]
    for u in anchor:
        lines += _render_unit(u)
    lines += ["## Customer-specific knowledge",
              "Definitions explain this customer's fields. Customer rules OVERRIDE the base "
              "policy whenever their 'Applies when' condition holds.", ""]
    if not custom:
        lines += ["(none yet)", ""]
    for u in custom:
        lines += _render_unit(u)
    lines += ["## Base triage policy (generic, applies to every customer)", ""]
    for u in base:
        lines += _render_unit(u)
    return "\n".join(lines)
