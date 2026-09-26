"""FDE retrospective + discovery playbook, wired to the store (fde_mode "retro").

- `run_retro` gathers the agent's own trail for this run (probes, findings, live
  units with provenance) plus the answer key, calls the pure `core.fde_retro.retro`,
  and appends the review to `fde_feedback`.
- `update_playbook` turns a cause that recurs across retro items into one general
  lesson in `method_lessons` (proposer model, structured output, linted). Lessons
  are method memory for the investigator/proposer; they are never triage units.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from harness.adapters.llm.openrouter import BudgetExceeded, LlmFailure, structured
from harness.adapters.mongo.client import app_db
from harness.config import get_settings
from harness.core.fde_retro import (
    FailedCase, FindingRecord, LiveUnit, ProbeRecord, RetroReview,
    causes_due_for_lesson, lint_lesson, retro,
)
from harness.core.fde import KeySignal
from harness.core.units import Unit

log = logging.getLogger(__name__)
PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "lesson_writer.md"


class LessonDraft(BaseModel):
    text: str = Field(description="one general sentence, no digits, no quoted strings")


async def _live_provenance(customer: str, units: list[Unit],
                           findings: list[FindingRecord]) -> list[LiveUnit]:
    db = app_db()
    out = []
    for u in units:
        if u.origin == "base" or u.layer == "anchor":
            continue
        d = await db["fde_decisions"].find_one({"customer": customer, "promoted": True,
                                                 "promoted_unit_hash": u.content_hash})
        p = await db["proposals"].find_one({"_id": d["proposal_id"]}) if d else None
        batch = int(d["batch"]) if d else 0
        paths = (set(u.applies_when.paths()) if u.applies_when else set()) | (
            {u.field} if u.field else set())
        ev = [f.evidence for f in findings if f.batch == batch
              and paths & (set(f.clause_paths) | ({f.field} if f.field else set()))]
        text = " ".join([*ev, (p or {}).get("hypothesis", "")])
        out.append(LiveUnit(unit=u, evidence_text=text,
                            sources=tuple((p or {}).get("evidence_refs", [])),
                            created_batch=batch))
    return out


async def _trail(customer: str) -> tuple[list[ProbeRecord], list[FindingRecord]]:
    db = app_db()
    probes = [ProbeRecord(tool=p["tool"], sources=tuple(p.get("sources") or ()),
                          args=dict(p.get("args") or {}))
              async for p in db["probes"].find({"customer": customer, "run_tag": "main"})
              .sort("_id", 1)]
    findings = [FindingRecord(kind=f["kind"], statement=f.get("statement", ""),
                              field=f.get("field") or "",
                              clause_paths=tuple(c["path"] for c in f.get("clauses") or ()),
                              sources=tuple(f.get("sources") or ()),
                              evidence=f.get("evidence", ""), batch=int(f["batch"]))
                async for f in db["findings"].find({"customer": customer, "run_tag": "main",
                                                     "empty": {"$ne": True}})]
    return probes, findings


async def _record_sources(customer: str) -> list[str]:
    doc = await app_db()["customers"].find_one({"_id": customer})
    return [m["source_id"] for m in (doc or {}).get("manifest", []) if m.get("kind") == "records"]


async def run_retro(
    *, customer: str, run_id: str, batch: int, phase: str, failed: list[FailedCase],
    units: list[Unit], key: list[KeySignal], records: list[dict[str, Any]],
    revealed_case_ids: set[str],
) -> dict[str, Any]:
    """Compute and append one retrospective. Returns the stored document."""
    probes, findings = await _trail(customer)
    live = await _live_provenance(customer, units, findings)
    review: RetroReview = retro(
        failed=failed, live_units=live, probes=probes, findings=findings, key=key,
        records=records, record_sources=await _record_sources(customer),
        revealed_case_ids=revealed_case_ids)
    doc = {"_id": f"{run_id}:retro:{batch}:{phase}", "customer": customer, "run_id": run_id,
           "batch": batch, "phase": phase, "fde_id": review.fde_id,
           "failed_cases": review.failed, "explained_cases": review.explained,
           "items": [{"cause": i.cause, "target_unit_id": i.target_unit_id,
                      "cases": list(i.cases), "n_cases": i.n_cases, "message": i.message,
                      "suggested_action": i.suggested_action} for i in review.items],
           "created_at": datetime.now(UTC)}
    await app_db()["fde_feedback"].insert_one(doc)
    return doc


async def active_lessons(customer: str, run_id: str) -> list[dict[str, Any]]:
    return [d async for d in app_db()["method_lessons"].find(
        {"customer": customer, "run_id": run_id, "status": "active"}).sort("created_batch", 1)]


async def update_playbook(*, customer: str, run_id: str, batch: int) -> list[dict[str, Any]]:
    """For each cause seen in >= 2 retro items this run with no active lesson, write one."""
    db = app_db()
    fb = [d async for d in db["fde_feedback"].find({"customer": customer, "run_id": run_id})
          .sort("created_at", 1)]
    items = [(d["_id"], it) for d in fb for it in d["items"]]
    active = await active_lessons(customer, run_id)
    due = causes_due_for_lesson([it["cause"] for _, it in items], [x["cause"] for x in active])
    written = []
    for cause in due:
        src = [(fid, it) for fid, it in items if it["cause"] == cause]
        fb_text = "\n".join(f"- {it['message']}" for _, it in src)
        system = PROMPT.read_text().split("-->", 1)[1].strip().format(cause=cause,
                                                                       feedback=fb_text)
        try:
            draft, _, _ = await structured(model=get_settings().proposer_model, system=system,
                                           user="Write the lesson.", schema=LessonDraft,
                                           max_tokens=300, purpose="lesson")
            text, why = draft.text.strip(), lint_lesson(draft.text)
        except (LlmFailure, BudgetExceeded) as e:
            text, why = "", f"writer failed: {type(e).__name__}"
        doc = {"_id": f"{run_id}:lesson:{cause}", "customer": customer, "run_id": run_id,
               "lesson_id": f"lesson.{cause}", "cause": cause, "text": text,
               "created_batch": batch, "source_feedback_ids": sorted({f for f, _ in src}),
               "status": "active" if why is None else "rejected_lint", "lint": why,
               "created_at": datetime.now(UTC)}
        if why is not None:
            # A rejected draft is kept for the audit trail under a distinct id per round,
            # so the cause can get another attempt after the next retro.
            doc["_id"] = f"{run_id}:lesson:{cause}:rejected:{batch}"
        await db["method_lessons"].replace_one({"_id": doc["_id"]}, doc, upsert=True)
        written.append(doc)
        log.info("%s lesson for %s: %s", customer, cause, "active" if why is None else why)
    return written
