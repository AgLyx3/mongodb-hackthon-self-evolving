"""Investigation agent: a small tool-calling loop over the probe toolbox.

Starts from the latest revealed failures, probes sources under a budget, and
submits findings (scoped rules or definitions) with the sources they rest on.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from harness.adapters.llm.openrouter import LlmFailure, chat_tools, structured
from harness.adapters.mongo.client import app_db
from harness.config import get_settings
from harness.core.units import Unit, render_harness
from harness.evolution.tools import TOOL_SPECS, Toolbox

PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "investigator_system.md"


class FindingClause(BaseModel):
    path: str
    op: Literal["==", "!=", ">=", "<=", ">", "<"]
    value: str


class Finding(BaseModel):
    kind: Literal["rule", "definition"]
    statement: str = Field(description="the finding in one or two sentences")
    field: str = Field(description="definition: the field it explains; rule: empty string")
    clauses: list[FindingClause] = Field(description="rule: AND-ed conditions; else empty")
    disposition: Literal["close_false_positive", "request_info", "escalate", "none"]
    sources: list[str] = Field(description="source ids the finding rests on")
    evidence: str = Field(description="the key numbers or quotes")


class Findings(BaseModel):
    findings: list[Finding]


SUBMIT_SPEC = {"type": "function", "function": {
    "name": "submit_findings", "description": "Submit your final findings (ends the "
    "investigation).", "parameters": Findings.model_json_schema()}}


def _template() -> str:
    t = PROMPT.read_text()
    return t.split("-->", 1)[1].strip()


async def manifest_text(customer: str) -> tuple[str, dict[str, str]]:
    doc = await app_db()["customers"].find_one({"_id": customer})
    assert doc is not None
    lines = [f"- {m['source_id']} ({m['kind']}): {m['described_as']}" for m in doc["manifest"]]
    lines.append("- customer_contact (ask_customer): the customer's contact for questions.")
    return "\n".join(lines), dict(doc["record_schema"])


def failures_text(failures: list[dict[str, Any]], limit: int = 14) -> str:
    out = []
    for f in failures[:limit]:
        out.append(f"- {f['case_id']}: agent said {f['predicted']}, correct is {f['label']}; "
                   f"applied {f['applied']}\n  record: {json.dumps(f['record'])}")
    return "\n".join(out) or "(none)"


def priors_text(priors: dict[str, float] | None) -> str:
    if not priors:
        return ""
    ranked = sorted(priors.items(), key=lambda kv: -kv[1])
    lines = [f"- {s}: {v:.1f}" for s, v in ranked]
    return ("## Where useful evidence came from before (learned for this customer; score = "
            "surviving harness changes it supported)\n" + "\n".join(lines))


async def investigate(
    *, customer: str, batch: int, units: list[Unit], failures: list[dict[str, Any]],
    revealed_batches: list[int], budget: int, priors: dict[str, float] | None,
    run_tag: str, max_turns: int = 14,
) -> tuple[list[Finding], Toolbox]:
    s = get_settings()
    manifest, glossary = await manifest_text(customer)
    system = _template().format(
        customer=customer, manifest=manifest, priors=priors_text(priors),
        glossary="\n".join(f"- {k}: {v}" for k, v in glossary.items()),
        harness=render_harness(units), failures=failures_text(failures), budget=budget)
    tb = Toolbox(customer, batch, run_tag, budget, revealed_batches)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": "Investigate the failures and submit findings."}]
    tools = [*TOOL_SPECS, SUBMIT_SPEC]
    for _ in range(max_turns):
        msg = await chat_tools(model=s.investigator_model, messages=messages, tools=tools,
                               purpose="investigate")
        calls = msg.get("tool_calls") or []
        messages.append({"role": "assistant", "content": msg.get("content") or "",
                         "tool_calls": calls} if calls else
                        {"role": "assistant", "content": msg.get("content") or ""})
        if not calls:
            break
        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            if name == "submit_findings":
                try:
                    return Findings.model_validate(args).findings, tb
                except Exception:  # noqa: BLE001 - fall through to structured fallback
                    result = json.dumps({"error": "invalid findings format"})
            else:
                result = await tb.call(name, args)
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": result})
    # The model stopped without submitting: ask for findings in structured form.
    transcript = "\n".join(str(m.get("content"))[:1500] for m in messages[2:] if m.get("content"))
    try:
        out, _, _ = await structured(
            model=s.investigator_model, system=system, schema=Findings, max_tokens=2000,
            user="Your probe results so far:\n" + transcript[-12000:] +
                 "\n\nSubmit your findings now.", purpose="investigate_final")
        return out.findings, tb
    except LlmFailure:
        return [], tb
