"""Structured `applies_when` conditions (decision 2).

A condition is a conjunction of clauses over dotted paths into a case record,
e.g. `account.age_months >= 24`. Structure is what lets the kernel check
activation deterministically, the simulated FDE narrow scope, and survival be
tracked per rule. Pure domain code: no I/O.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel

Op = Literal["==", "!=", ">=", "<=", ">", "<", "in"]
Disposition = Literal["close_false_positive", "request_info", "escalate"]
DISPOSITIONS: tuple[Disposition, ...] = ("close_false_positive", "request_info", "escalate")


class Clause(BaseModel, frozen=True):
    path: str
    op: Op
    value: Any

    def render(self) -> str:
        return f"{self.path} {self.op} {self.value!r}"


class Condition(BaseModel, frozen=True):
    all_of: tuple[Clause, ...]

    def render(self) -> str:
        return " AND ".join(c.render() for c in self.all_of) or "always"

    def paths(self) -> frozenset[str]:
        return frozenset(c.path for c in self.all_of)


def get_path(record: dict[str, Any], path: str) -> Any:
    cur: Any = record
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _coerce(left: Any, right: Any) -> tuple[Any, Any]:
    # Dates are stored as ISO strings in records; compare as dates when both parse.
    if isinstance(left, str) and isinstance(right, str):
        try:
            return date.fromisoformat(left[:10]), date.fromisoformat(right[:10])
        except ValueError:
            return left, right
    return left, right


def clause_holds(record: dict[str, Any], clause: Clause) -> bool:
    left = get_path(record, clause.path)
    if left is None:
        return False
    if clause.op == "in":
        return left in clause.value
    left, right = _coerce(left, clause.value)
    try:
        match clause.op:
            case "==":
                return bool(left == right)
            case "!=":
                return bool(left != right)
            case ">=":
                return bool(left >= right)
            case "<=":
                return bool(left <= right)
            case ">":
                return bool(left > right)
            case "<":
                return bool(left < right)
    except TypeError:
        return False
    return False


def holds(record: dict[str, Any], condition: Condition) -> bool:
    return all(clause_holds(record, c) for c in condition.all_of)
