"""Runtime triage agent: one structured LLM call per alert (decision 9: case-only).

The system prompt is the rendered harness, which is the part that evolves.
Deep Agents is used for the investigator; triage runs thousands of times, so
it is a lean single call to keep the $10 budget (TASKS.md, 2026-09-26).
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from harness.adapters.llm.openrouter import structured
from harness.core.conditions import Disposition
from harness.core.units import Unit, render_harness

PROMPT = Path(__file__).resolve().parents[2] / "prompts" / "triage_system.md"


class TriageResult(BaseModel):
    disposition: Disposition
    applied_unit_ids: list[str] = Field(
        description="ids of the harness sections you relied on, e.g. base.large_amount")
    rationale: str = Field(description="one sentence")


@cache
def _template() -> str:
    text = PROMPT.read_text()
    return text.split("-->", 1)[1].strip() if "-->" in text else text


def system_prompt(units: list[Unit]) -> str:
    return _template().replace("{harness}", render_harness(units))


def user_prompt(record: dict[str, Any], glossary: dict[str, str]) -> str:
    gl = "\n".join(f"- {k}: {v}" for k, v in glossary.items())
    return (f"Field glossary (from customer onboarding):\n{gl}\n\n"
            f"Alert records:\n```json\n{json.dumps(record, indent=1)}\n```\n\n"
            "Decide the disposition for this alert.")


async def triage(
    units: list[Unit], record: dict[str, Any], glossary: dict[str, str], *, model: str,
    rep: int = 0,
) -> tuple[TriageResult, float, bool]:
    return await structured(model=model, system=system_prompt(units),
                            user=user_prompt(record, glossary), schema=TriageResult,
                            max_tokens=3000, rep=rep, purpose="triage")
