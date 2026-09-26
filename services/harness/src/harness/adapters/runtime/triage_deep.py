"""Deep Agents triage runtime: the deployed triage agent as a LangChain Deep Agent.

- Instructions: the rendered harness (triage.system_prompt(units)), the evolving part.
- Case scope (decision 9): the agent sees the alert section inline and fetches the
  other top-level sections of *this* case through two tools. The record reaches the
  tools only via the per-invocation runtime context, so nothing outside the case is
  reachable.
- State: every run is checkpointed to MongoDB Atlas (langgraph-checkpoint-mongodb),
  collections `triage_checkpoints` / `triage_checkpoint_writes`, thread id
  f"{tag}:{case_id}:{version}:{rep}".
- Cost: final results are cached in `llm_cache` (unchanged harness + case = $0); every
  paid model response is `$inc`ed into the `llm_spend` ledger and logged to `llm_calls`
  (purpose "triage_deep"); model calls refuse to start once the ledger reaches the
  limit. Prompts and completions are never logged.
- Built-in Deep Agents scaffolding: the filesystem tools, `execute`, the `task`
  subagent tool and summarization are switched off through a HarnessProfile.
  FilesystemMiddleware itself cannot be removed (deepagents marks it required), but
  with its tools excluded it adds nothing to the request.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    create_deep_agent,
    register_harness_profile,
)
from langchain.tools import ToolRuntime
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import LLMResult
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from harness.adapters.llm.openrouter import BudgetExceeded, LlmFailure, spent_usd
from harness.adapters.mongo.client import app_db
from harness.adapters.runtime.triage import TriageResult, system_prompt
from harness.config import get_settings
from harness.core.units import Unit

log = logging.getLogger(__name__)

RUNTIME = "deep"
PURPOSE = "triage_deep"
PROMPT = Path(__file__).resolve().parents[2] / "prompts" / "triage_deep_user.md"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
CHECKPOINTS = "triage_checkpoints"
CHECKPOINT_WRITES = "triage_checkpoint_writes"
INLINE_SECTION = "alert"
MAX_TOKENS = 1500
RECURSION_LIMIT = 30  # graph supersteps; a triage needs ~2 per model/tool round
# Built-in Deep Agents tools the triage agent must not have (case-only, no workspace).
EXCLUDED_TOOLS = frozenset(
    {"ls", "read_file", "write_file", "edit_file", "delete", "glob", "grep", "execute",
     "write_todos", "task"})
_SEM = asyncio.Semaphore(8)
_AGENT_CACHE_MAX = 32


# ---------------------------------------------------------------- record sectioning
# Pure functions: the tools are thin wrappers over these (tested without network).

def inline_section(record: dict[str, Any]) -> str:
    """The section shown inline: `alert` when the customer's record has one, else the
    record's first top-level key (records differ per customer)."""
    if INLINE_SECTION in record:
        return INLINE_SECTION
    return next(iter(record), "")


def other_sections(record: dict[str, Any]) -> list[str]:
    inline = inline_section(record)
    return [k for k in record if k != inline]


def list_sections_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {"inline_section": inline_section(record), "fetchable_sections": other_sections(record)}


def section_payload(record: dict[str, Any], section: Any) -> dict[str, Any]:
    """Return one top-level section of this case, or a structured error. Never raises."""
    if not isinstance(section, str) or not section.strip():
        return {"error": "invalid_section", "detail": "section must be a non-empty string",
                "available": list(record)}
    name = section.strip()
    if name not in record:
        return {"error": "unknown_section", "section": name, "available": list(record)}
    return {"section": name, "fields": record[name]}


# ------------------------------------------------------------------------- tools

@dataclass(frozen=True)
class CaseContext:
    """Per-invocation runtime context: the one case this run may read."""
    record: dict[str, Any]


def _ctx_record(runtime: ToolRuntime[CaseContext]) -> dict[str, Any] | None:
    ctx = getattr(runtime, "context", None)
    return ctx.record if isinstance(ctx, CaseContext) else None


@tool
def list_record_sections(runtime: ToolRuntime[CaseContext]) -> str:
    """List the top-level sections of the case record for the alert you are triaging.

    Returns JSON: {"inline_section": <name already shown to you>,
    "fetchable_sections": [<names you can pass to get_record_section>]}.
    Only this one case is reachable; there is no search across cases.
    """
    record = _ctx_record(runtime)
    if record is None:
        return json.dumps({"error": "no_case_loaded"})
    return json.dumps(list_sections_payload(record))


@tool
def get_record_section(section: str, runtime: ToolRuntime[CaseContext]) -> str:
    """Fetch one top-level section of the case record for the alert you are triaging.

    Args:
        section: exact section name, as listed in the task message or returned by
            list_record_sections (for example "txn" or "account"; names differ by
            customer).

    Returns JSON {"section": <name>, "fields": {...}} with that section's fields, or
    {"error": "unknown_section" | "invalid_section", "available": [...]} if the name is
    not a section of this case. Only this one case is reachable.
    """
    record = _ctx_record(runtime)
    if record is None:
        return json.dumps({"error": "no_case_loaded"})
    return json.dumps(section_payload(record, section), default=str)


TOOLS = [list_record_sections, get_record_section]


# -------------------------------------------------------------------- prompt / key

@cache
def _user_template() -> str:
    text = PROMPT.read_text()
    return text.split("-->", 1)[1].strip() if "-->" in text else text


def user_message(record: dict[str, Any], glossary: dict[str, str]) -> str:
    inline = inline_section(record)
    rest = other_sections(record)
    return (_user_template()
            .replace("{glossary}", "\n".join(f"- {k}: {v}" for k, v in glossary.items()))
            .replace("{inline}", inline)
            .replace("{record}", json.dumps(record.get(inline, {}), indent=1, default=str))
            .replace("{sections}", ", ".join(rest) if rest else "(none)"))


def cache_key(*, model: str, harness_text: str, record: dict[str, Any],
              glossary: dict[str, str], rep: int) -> str:
    """Result-cache key: runtime, model, rendered harness, case record, glossary, the
    task template and rep. Deterministic across processes (sorted-key JSON)."""
    blob = json.dumps([RUNTIME, model, harness_text, record, glossary, _user_template(),
                       TriageResult.__name__, TriageResult.model_json_schema(), rep],
                      sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def thread_id(*, tag: str, case_id: str, version: str, rep: int) -> str:
    return f"{tag}:{case_id}:{version}:{rep}"


# -------------------------------------------------------------- model / checkpointer

@cache
def _model(model: str) -> ChatOpenAI:
    s = get_settings()
    assert s.openrouter_api_key is not None, "OPENROUTER_API_KEY missing"
    return ChatOpenAI(
        base_url=OPENROUTER_BASE_URL, api_key=s.openrouter_api_key, model=model,
        temperature=0, max_completion_tokens=MAX_TOKENS, timeout=60, max_retries=2,
        use_responses_api=False, default_headers={"X-Title": "fde-harness"},
        extra_body={"usage": {"include": True}})


@cache
def _register_profile(model: str) -> None:
    """Strip the built-in Deep Agents workspace from the triage agent for this model."""
    register_harness_profile(f"openai:{model}", HarnessProfile(
        excluded_tools=EXCLUDED_TOOLS,
        excluded_middleware=frozenset({"SummarizationMiddleware"}),
        general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)))


_checkpointer: Any = None
_cp_lock = asyncio.Lock()


async def checkpointer() -> Any:
    """MongoDBSaver on the app database, built once (its constructor creates indexes,
    a blocking call, so it runs off the event loop). langgraph-checkpoint-mongodb 0.5
    ships only the sync saver; its a* methods run the sync client in an executor."""
    global _checkpointer
    async with _cp_lock:
        if _checkpointer is None:
            from langgraph.checkpoint.mongodb import MongoDBSaver
            from pymongo import MongoClient

            s = get_settings()

            def build() -> Any:
                client: MongoClient[dict[str, Any]] = MongoClient(
                    s.mongodb_uri_app.get_secret_value(), appname="fde-triage-deep")
                return MongoDBSaver(client, db_name=s.mongodb_db,
                                    checkpoint_collection_name=CHECKPOINTS,
                                    writes_collection_name=CHECKPOINT_WRITES)

            _checkpointer = await asyncio.to_thread(build)
    return _checkpointer


_agents: dict[tuple[str, str], Any] = {}


async def agent_for(model: str, harness_text: str) -> Any:
    """One compiled Deep Agent per (model, harness version), reused across cases."""
    key = (model, hashlib.sha256(harness_text.encode()).hexdigest())
    if key not in _agents:
        _register_profile(model)
        agent = create_deep_agent(
            model=_model(model), tools=TOOLS, system_prompt=harness_text,
            response_format=TriageResult, context_schema=CaseContext,
            checkpointer=await checkpointer(), name="triage")
        if len(_agents) >= _AGENT_CACHE_MAX:
            _agents.pop(next(iter(_agents)))
        _agents[key] = agent
    return _agents[key]


# ------------------------------------------------------------------ spend ledger

def usage_from_result(result: LLMResult) -> tuple[float, int | None, int | None]:
    """(cost_usd, prompt_tokens, completion_tokens) from one ChatOpenAI response.
    OpenRouter returns `usage.cost`; ChatOpenAI keeps the raw usage in llm_output."""
    usage = (result.llm_output or {}).get("token_usage") or {}
    cost = float(usage.get("cost") or 0.0)
    pin, pout = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if pin is None:
        for gens in result.generations:
            for g in gens:
                um = getattr(getattr(g, "message", None), "usage_metadata", None)
                if um:
                    pin, pout = um.get("input_tokens"), um.get("output_tokens")
    return cost, pin, pout


class SpendLedger(AsyncCallbackHandler):
    """Budget stop before, ledger + llm_calls after, every model response of one run."""

    raise_error = True  # a BudgetExceeded in on_chat_model_start must abort the run

    def __init__(self, model: str, thread: str) -> None:
        self.model, self.thread = model, thread
        self.cost, self.in_tokens, self.out_tokens, self.calls = 0.0, 0, 0, 0

    async def on_chat_model_start(self, serialized: dict[str, Any],
                                  messages: list[list[Any]], **kwargs: Any) -> None:
        limit = get_settings().llm_spend_limit_usd
        if await spent_usd() >= limit:
            raise BudgetExceeded(f"LLM spend reached ${limit:.2f}")

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        cost, pin, pout = usage_from_result(response)
        self.cost += cost
        self.in_tokens += pin or 0
        self.out_tokens += pout or 0
        self.calls += 1
        db = app_db()
        await db["llm_spend"].update_one(
            {"_id": "ledger"}, {"$inc": {"usd": cost, "calls": 1}}, upsert=True)
        await db["llm_calls"].insert_one({
            "model": self.model, "purpose": PURPOSE, "cost": cost, "in_tokens": pin,
            "out_tokens": pout, "thread_id": self.thread})


# ------------------------------------------------------------------------- run

@dataclass
class DeepRun:
    result: TriageResult
    cost: float
    cache_hit: bool
    thread_id: str = ""
    model_calls: int = 0
    tool_calls: int = 0
    in_tokens: int = 0
    out_tokens: int = 0


def count_tool_calls(messages: list[Any]) -> int:
    """Case-tool calls made by the agent (the structured-output tool is not counted)."""
    return sum(1 for m in messages if isinstance(m, AIMessage)
               for tc in (m.tool_calls or []) if tc.get("name") != TriageResult.__name__)


async def _free_thread(cp: Any, base: str) -> tuple[str, TriageResult | None]:
    """The thread id to run on. If `base` already holds a finished run, return its
    result; if it holds an unfinished one (a failed earlier attempt), use a fresh
    suffix so the retry does not resume a half-finished conversation."""
    tid, n = base, 0
    while True:
        tup = await cp.aget_tuple({"configurable": {"thread_id": tid, "checkpoint_ns": ""}})
        if tup is None:
            return tid, None
        done = (tup.checkpoint.get("channel_values") or {}).get("structured_response")
        if isinstance(done, TriageResult):
            return tid, done
        n += 1
        tid = f"{base}:a{n}"


async def run(
    units: list[Unit], record: dict[str, Any], glossary: dict[str, str], *, model: str,
    rep: int = 0, case_id: str = "", tag: str = "", version: str = "",
) -> DeepRun:
    harness_text = system_prompt(units)
    key = cache_key(model=model, harness_text=harness_text, record=record,
                    glossary=glossary, rep=rep)
    db = app_db()
    hit = await db["llm_cache"].find_one({"_id": key})
    if hit is not None:
        return DeepRun(TriageResult.model_validate(hit["parsed"]), 0.0, True)

    limit = get_settings().llm_spend_limit_usd
    if await spent_usd() >= limit:
        raise BudgetExceeded(f"LLM spend reached ${limit:.2f}")

    version = version or hashlib.sha256(harness_text.encode()).hexdigest()[:16]
    cp = await checkpointer()
    tid, done = await _free_thread(
        cp, thread_id(tag=tag, case_id=case_id or key[:12], version=version, rep=rep))
    if done is not None:
        await _store(key, done, model)
        return DeepRun(done, 0.0, True, thread_id=tid)

    agent = await agent_for(model, harness_text)
    ledger = SpendLedger(model, tid)
    config: dict[str, Any] = {"configurable": {"thread_id": tid},
                              "callbacks": [ledger], "recursion_limit": RECURSION_LIMIT}
    try:
        async with _SEM:
            out = await agent.ainvoke(
                {"messages": [HumanMessage(user_message(record, glossary))]},
                config=config, context=CaseContext(record=record))
    except BudgetExceeded:
        raise
    except Exception as e:  # provider/format/recursion failures are not the harness
        log.warning("deep triage failed thread=%s err=%s", tid, type(e).__name__)
        raise LlmFailure(f"deep triage failed: {type(e).__name__}") from e

    parsed = out.get("structured_response")
    if not isinstance(parsed, TriageResult):
        log.warning("deep triage returned no structured response thread=%s", tid)
        raise LlmFailure("deep triage: no structured response")
    await _store(key, parsed, model)
    return DeepRun(parsed, ledger.cost, False, thread_id=tid, model_calls=ledger.calls,
                   tool_calls=count_tool_calls(out.get("messages") or []),
                   in_tokens=ledger.in_tokens, out_tokens=ledger.out_tokens)


async def _store(key: str, parsed: TriageResult, model: str) -> None:
    await app_db()["llm_cache"].update_one(
        {"_id": key}, {"$set": {"parsed": parsed.model_dump(mode="json"), "model": model,
                                "runtime": RUNTIME}}, upsert=True)


async def triage(
    units: list[Unit], record: dict[str, Any], glossary: dict[str, str], *, model: str,
    rep: int = 0, case_id: str = "", tag: str = "", version: str = "",
) -> tuple[TriageResult, float, bool]:
    """Same contract as triage.triage(): (result, cost_usd, cache_hit)."""
    r = await run(units, record, glossary, model=model, rep=rep, case_id=case_id, tag=tag,
                  version=version)
    return r.result, r.cost, r.cache_hit
