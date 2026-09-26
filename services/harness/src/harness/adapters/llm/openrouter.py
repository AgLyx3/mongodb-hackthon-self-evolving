"""OpenRouter structured-output calls with a response cache and a hard spend stop.

Direct httpx client (langchain-openrouter's async path hung under load on
2026-09-26). Structured output via `response_format: json_schema` (strict).

- Cache: Mongo `llm_cache`, keyed by (model, system, user, schema, rep). `rep`
  lets noise-band runs make genuinely repeated calls.
- Spend: every paid call `$inc`s a single ledger doc; calls refuse to start
  once the ledger reaches LLM_SPEND_LIMIT_USD. Cost comes from OpenRouter's
  `usage.cost`. Prompts and completions are never logged.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
from functools import lru_cache
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from harness.adapters.mongo.client import app_db
from harness.config import get_settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)
URL = "https://openrouter.ai/api/v1/chat/completions"
_SEM = asyncio.Semaphore(8)


class BudgetExceeded(Exception):
    pass


class LlmFailure(Exception):
    pass


@lru_cache
def _client() -> httpx.AsyncClient:
    key = get_settings().openrouter_api_key
    assert key is not None, "OPENROUTER_API_KEY missing"
    return httpx.AsyncClient(
        headers={"Authorization": f"Bearer {key.get_secret_value()}",
                 "X-Title": "fde-harness"},
        timeout=httpx.Timeout(60.0, connect=10.0))


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic JSON schema made strict-mode compatible (all required, no extras)."""
    schema = copy.deepcopy(model.model_json_schema())

    def fix(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            # Drop schema metadata, but never a *property* that happens to be named
            # "title" or "default" (those live inside the "properties" mapping).
            if not isinstance(node.get("title"), dict):
                node.pop("title", None)
            if not isinstance(node.get("default"), dict):
                node.pop("default", None)
            for v in node.values():
                fix(v)
        elif isinstance(node, list):
            for v in node:
                fix(v)

    fix(schema)
    return schema


def _key(model: str, system: str, user: str, schema: type[BaseModel], rep: int) -> str:
    blob = json.dumps([model, system, user, schema.__name__,
                       schema.model_json_schema(), rep], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


async def spent_usd() -> float:
    doc = await app_db()["llm_spend"].find_one({"_id": "ledger"})
    return float(doc["usd"]) if doc else 0.0


async def _call(body: dict[str, Any]) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(3):
        try:
            async with _SEM:
                r = await _client().post(URL, json=body)
            if r.status_code == 200:
                data: dict[str, Any] = r.json()
                if data.get("choices"):
                    return data
                last = LlmFailure(f"no choices: {str(data.get('error'))[:200]}")
            elif r.status_code in (400, 401, 402, 403):
                raise LlmFailure(f"http {r.status_code}: {r.text[:200]}")
            else:
                last = LlmFailure(f"http {r.status_code}")
        except httpx.HTTPError as e:
            last = e
        log.warning("llm call retry attempt=%d err=%s", attempt, type(last).__name__)
        await asyncio.sleep(2 * (attempt + 1))
    raise LlmFailure(f"provider call failed after retries: {type(last).__name__}")


async def structured(
    *, model: str, system: str, user: str, schema: type[T], max_tokens: int = 600,
    temperature: float = 0.0, rep: int = 0, purpose: str = "",
) -> tuple[T, float, bool]:
    """Return (parsed, cost_usd, cache_hit)."""
    db = app_db()
    key = _key(model, system, user, schema, rep)
    hit = await db["llm_cache"].find_one({"_id": key})
    if hit is not None:
        return schema.model_validate(hit["parsed"]), 0.0, True

    limit = get_settings().llm_spend_limit_usd
    if await spent_usd() >= limit:
        raise BudgetExceeded(f"LLM spend reached ${limit:.2f}")

    data = await _call({
        "model": model, "max_tokens": max_tokens, "temperature": temperature,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": schema.__name__, "strict": True, "schema": strict_schema(schema)}},
    })
    usage = data.get("usage") or {}
    cost = float(usage.get("cost") or 0.0)
    await db["llm_spend"].update_one(
        {"_id": "ledger"}, {"$inc": {"usd": cost, "calls": 1}}, upsert=True)
    await db["llm_calls"].insert_one({
        "model": model, "purpose": purpose, "cost": cost,
        "in_tokens": usage.get("prompt_tokens"), "out_tokens": usage.get("completion_tokens")})

    content = data["choices"][0]["message"].get("content") or ""
    try:
        parsed = schema.model_validate_json(_strip_fences(content))
    except ValidationError as e:
        log.warning("structured output invalid purpose=%s model=%s", purpose, model)
        raise LlmFailure("invalid structured output") from e
    await db["llm_cache"].update_one(
        {"_id": key}, {"$set": {"parsed": parsed.model_dump(mode="json"), "model": model}},
        upsert=True)
    return parsed, cost, False


async def chat_tools(
    *, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
    max_tokens: int = 1500, purpose: str = "",
) -> dict[str, Any]:
    """One tool-calling turn (not cached: agent loops depend on live tool results).
    Returns the assistant message dict."""
    limit = get_settings().llm_spend_limit_usd
    if await spent_usd() >= limit:
        raise BudgetExceeded(f"LLM spend reached ${limit:.2f}")
    data = await _call({"model": model, "max_tokens": max_tokens, "temperature": 0.2,
                        "messages": messages, "tools": tools})
    usage = data.get("usage") or {}
    cost = float(usage.get("cost") or 0.0)
    db = app_db()
    await db["llm_spend"].update_one(
        {"_id": "ledger"}, {"$inc": {"usd": cost, "calls": 1}}, upsert=True)
    await db["llm_calls"].insert_one({
        "model": model, "purpose": purpose, "cost": cost,
        "in_tokens": usage.get("prompt_tokens"), "out_tokens": usage.get("completion_tokens")})
    msg: dict[str, Any] = data["choices"][0]["message"]
    return msg


def _strip_fences(text: str) -> str:
    """Extract the JSON object even if the model wrapped it in prose or fences."""
    t = text.strip()
    start, end = t.find("{"), t.rfind("}")
    return t[start:end + 1] if start != -1 and end > start else t
