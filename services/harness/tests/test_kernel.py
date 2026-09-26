import pytest

from harness.core.conditions import Clause, Condition
from harness.core.kernel import (
    Change,
    FdeDecision,
    KernelError,
    Proposal,
    promote,
    unit_edit_distance,
)
from harness.core.units import Unit, make_version, render_harness


def _unit(uid: str, layer: str = "truth", value: int = 180) -> Unit:
    return Unit(
        unit_id=uid, kind="rule", layer=layer, title=uid, text="escalate sleepers",  # type: ignore[arg-type]
        applies_when=Condition(all_of=(Clause(path="account.dormant_days", op=">=", value=value),)),
        disposition="escalate",
    )


BASE = [_unit("base.a"), _unit("base.guard", layer="anchor", value=1)]
V0 = make_version("bank", BASE, None, "base")


def _proposal(change: Change, parent: str = V0.version_hash) -> Proposal:
    return Proposal(proposal_id="p1", customer="bank", batch=1, parent_version=parent,
                    change=change, hypothesis="h", falsification_criterion="f")


def _decision(action: str, final: Unit | None = None) -> FdeDecision:
    return FdeDecision(proposal_id="p1", action=action, reason_tag="correct",  # type: ignore[arg-type]
                       rationale="r", final_unit=final)


def test_content_hash_is_stable_and_ignores_origin():
    a = _unit("x")
    assert a.content_hash == _unit("x").content_hash
    assert a.content_hash == a.model_copy(update={"origin": "fde_edit"}).content_hash
    assert a.content_hash != _unit("x", value=90).content_hash


def test_accept_creates_new_version_with_parent_edge():
    units, v1 = promote(_proposal(Change(add=_unit("new"))), _decision("accept"), BASE, V0)
    assert v1.parent == V0.version_hash and v1.edge == "extends"
    assert v1.version_hash != V0.version_hash
    assert {u.unit_id for u in units} == {"base.a", "base.guard", "new"}


@pytest.mark.parametrize("action", ["reject", "defer"])
def test_promotion_requires_accept_or_edit(action):
    with pytest.raises(KernelError):
        promote(_proposal(Change(add=_unit("new"))), _decision(action), BASE, V0)


def test_noop_change_is_rejected():
    with pytest.raises(KernelError):
        promote(_proposal(Change(add=_unit("base.a"))), _decision("accept"), BASE, V0)


def test_edit_promotes_the_fde_version_not_the_proposal():
    narrowed = _unit("new", value=365)
    units, _ = promote(_proposal(Change(add=_unit("new"))), _decision("edit", narrowed),
                       BASE, V0)
    live = {u.unit_id: u for u in units}["new"]
    assert live.content_hash == narrowed.content_hash and live.origin == "fde_edit"


def test_anchor_units_cannot_be_added_or_retired():
    guard = BASE[1]
    with pytest.raises(KernelError):
        promote(_proposal(Change(retire_hash=guard.content_hash)), _decision("accept"), BASE, V0)
    with pytest.raises(KernelError):
        promote(_proposal(Change(add=_unit("evil", layer="anchor"))), _decision("accept"),
                BASE, V0)


def test_stale_parent_is_rejected():
    with pytest.raises(KernelError):
        promote(_proposal(Change(add=_unit("new")), parent="deadbeef"), _decision("accept"),
                BASE, V0)


def test_retire_and_supersede_edges():
    units, v1 = promote(_proposal(Change(add=_unit("new"))), _decision("accept"), BASE, V0)
    new = {u.unit_id: u for u in units}["new"]
    p2 = Proposal(proposal_id="p2", customer="bank", batch=2, parent_version=v1.version_hash,
                  change=Change(retire_hash=new.content_hash), hypothesis="h",
                  falsification_criterion="f")
    d2 = FdeDecision(proposal_id="p2", action="accept", reason_tag="correct", rationale="r")
    units2, v2 = promote(p2, d2, units, v1)
    assert v2.edge == "retires" and {u.unit_id for u in units2} == {"base.a", "base.guard"}
    # Same content as v0 means the same version hash: rollback-by-content is detectable.
    assert v2.version_hash == V0.version_hash


def test_edit_distance_bounds():
    a = _unit("x")
    assert unit_edit_distance(a, a) == 0.0
    assert 0 < unit_edit_distance(a, _unit("x", value=365)) < 0.5


def test_render_includes_scope_and_disposition():
    text = render_harness(BASE)
    assert "Applies when: account.dormant_days >= 180" in text
    assert "Disposition: escalate" in text
