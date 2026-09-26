"""Shared types for generated customers: signals, answer key, sources, cases."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from harness.core.conditions import Condition, Disposition

SourceKind = Literal["records", "qc_sheet", "doc", "interview", "chat", "export"]


class Signal(BaseModel):
    """One planted piece of customer truth. The answer key the FDE judges against."""

    signal_id: str
    customer: str
    shared: bool  # the one pattern planted in every customer (decision 11)
    kind: Literal["rule", "definition"]
    description: str
    condition: Condition | None = None  # rules
    disposition: Disposition | None = None  # rules
    field: str | None = None  # definitions: which field it explains
    meaning_keywords: tuple[str, ...] = ()  # definitions: what a correct meaning mentions
    locations: tuple[str, ...]  # source ids where the evidence lives
    signal_type: str  # e.g. "qc_pattern", "interview_remark", "cryptic_code"


class SourceEntry(BaseModel):
    source_id: str
    kind: SourceKind
    described_as: str  # what the customer said at onboarding (may be wrong)
    relevant: bool  # answer-key only: decoys are False


class Chunk(BaseModel):
    source_id: str
    kind: SourceKind
    text: str
    meta: dict[str, Any] = {}


class Case(BaseModel):
    case_id: str
    customer: str
    record: dict[str, Any]
    label: Disposition
    case_type: str  # signal id or "base.*"; answer-key only
    split: Literal["history", "batch1", "batch2", "batch3", "holdout"]


class Customer(BaseModel):
    customer: str
    display_name: str
    industry: str
    record_schema: dict[str, str]  # field path -> description shown in source profiles
    manifest: list[SourceEntry]
    signals: list[Signal]
    oracle: dict[str, str]  # keyword -> answer, for targeted questions
    cases: list[Case]
    history_labels: dict[str, Disposition]  # case_id -> label, for labeled history rows
    chunks: list[Chunk]
