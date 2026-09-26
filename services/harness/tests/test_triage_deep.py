"""Deep Agents triage runtime: case-scoped tools, cache key, runtime switch. No network."""

import json
from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult, LLMResult
from langchain_openai import ChatOpenAI

from harness.adapters.runtime import triage as single_runtime
from harness.adapters.runtime import triage_deep as td
from harness.adapters.runtime.triage import TriageResult
from harness.config import Settings
from harness.evolution import evaluate

BANK = {
    "alert": {"alert_id": "A1", "alert_type": "large_txn"},
    "txn": {"amount_usd": 51566.4, "purpose_code": "GDS"},
    "account": {"kyc_status": "complete", "dormant_days": 60},
}
FINTECH = {"txn": {"amount": 10}, "wallet": {"age_days": 3}}


def _rt(record: dict[str, Any] | None) -> Any:
    return SimpleNamespace(context=None if record is None else td.CaseContext(record=record))


def test_inline_section_is_alert_else_first_key():
    assert td.inline_section(BANK) == "alert"
    assert td.other_sections(BANK) == ["txn", "account"]
    assert td.inline_section(FINTECH) == "txn"
    assert td.other_sections(FINTECH) == ["wallet"]


def test_get_record_section_returns_only_that_section_of_this_case():
    out = json.loads(td.get_record_section.func(section="txn", runtime=_rt(BANK)))
    assert out == {"section": "txn", "fields": BANK["txn"]}
    other = json.loads(td.get_record_section.func(section="wallet", runtime=_rt(FINTECH)))
    assert other["fields"] == FINTECH["wallet"]


@pytest.mark.parametrize("bad", ["wallet", "TXN", "", "   ", "../txn"])
def test_unknown_section_is_a_structured_error(bad):
    out = json.loads(td.get_record_section.func(section=bad, runtime=_rt(BANK)))
    assert out["error"] in {"unknown_section", "invalid_section"}
    assert out["available"] == ["alert", "txn", "account"]
    assert "fields" not in out


def test_non_string_section_does_not_raise():
    assert td.section_payload(BANK, None)["error"] == "invalid_section"
    assert td.section_payload(BANK, 3)["error"] == "invalid_section"


def test_tools_without_a_case_return_error():
    assert json.loads(td.list_record_sections.func(runtime=_rt(None))) == {
        "error": "no_case_loaded"}
    assert json.loads(td.get_record_section.func(section="txn", runtime=_rt(None)))["error"] \
        == "no_case_loaded"


def test_list_record_sections_lists_this_case_only():
    out = json.loads(td.list_record_sections.func(runtime=_rt(BANK)))
    assert out == {"inline_section": "alert", "fetchable_sections": ["txn", "account"]}


def test_user_message_inlines_only_the_alert_section():
    msg = td.user_message(BANK, {"amount_usd": "transaction amount"})
    assert "large_txn" in msg and "txn, account" in msg
    assert "51566.4" not in msg and "dormant_days" not in msg
    assert "- amount_usd: transaction amount" in msg


def test_cache_key_is_deterministic_and_sensitive():
    base: dict[str, Any] = {"model": "m", "harness_text": "H", "record": BANK,
                            "glossary": {"a": "b"}, "rep": 0}
    k = td.cache_key(**base)
    reordered = dict(reversed(list(BANK.items())))
    assert k == td.cache_key(**{**base, "record": reordered})  # key order irrelevant
    for change in ({"rep": 1}, {"harness_text": "H2"}, {"model": "m2"},
                   {"record": {**BANK, "txn": {"amount_usd": 1}}}):
        assert td.cache_key(**{**base, **change}) != k


def test_thread_id_format():
    assert td.thread_id(tag="noise", case_id="NB-1", version="abc", rep=2) == "noise:NB-1:abc:2"


def test_usage_reads_openrouter_cost():
    res = LLMResult(generations=[[]], llm_output={"token_usage": {
        "cost": 0.0012, "prompt_tokens": 900, "completion_tokens": 50}})
    assert td.usage_from_result(res) == (0.0012, 900, 50)
    assert td.usage_from_result(LLMResult(generations=[[]], llm_output=None))[0] == 0.0


def test_select_runtime(monkeypatch):
    assert evaluate.select_runtime("single") == ("single", single_runtime.triage)
    assert evaluate.select_runtime("deep") == ("deep", td.triage)
    with pytest.raises(ValueError):
        evaluate.select_runtime("bogus")
    monkeypatch.setattr(evaluate, "get_settings", lambda: SimpleNamespace(triage_runtime="deep"))
    assert evaluate.select_runtime()[0] == "deep"


def test_settings_triage_runtime_from_env(monkeypatch):
    kw: dict[str, Any] = {"mongodb_uri_app": "x", "mongodb_uri_proposer": "y", "_env_file": None}
    monkeypatch.delenv("TRIAGE_RUNTIME", raising=False)
    assert Settings(**kw).triage_runtime == "single"
    monkeypatch.setenv("TRIAGE_RUNTIME", "deep")
    assert Settings(**kw).triage_runtime == "deep"
    monkeypatch.setenv("TRIAGE_RUNTIME", "other")
    with pytest.raises(ValueError):
        Settings(**kw)


def test_profile_strips_builtin_deep_agent_tools():
    """The model sees only the two case tools plus the structured-output tool."""
    from deepagents import create_deep_agent

    seen: dict[str, Any] = {}

    class Fake(ChatOpenAI):
        def bind_tools(self, tools: Any, **kw: Any) -> Any:
            from langchain_core.utils.function_calling import convert_to_openai_tool
            seen["tools"] = [convert_to_openai_tool(t)["function"]["name"] for t in tools]
            return super().bind_tools(tools, **kw)

        def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None,
                      **k: Any) -> ChatResult:
            seen["system"] = messages[0].content
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=[
                {"name": "TriageResult", "id": "1", "args": {
                    "disposition": "escalate", "applied_unit_ids": [], "rationale": "x"}}]))])

    model = "test/deep-profile-model"
    td._register_profile(model)
    agent = create_deep_agent(
        model=Fake(model=model, api_key="x", base_url="http://127.0.0.1:9"), tools=td.TOOLS,
        system_prompt="HARNESS", response_format=TriageResult, context_schema=td.CaseContext)
    out = agent.invoke({"messages": [{"role": "user", "content": "go"}]},
                       context=td.CaseContext(record=BANK))
    assert seen["tools"] == ["list_record_sections", "get_record_section", "TriageResult"]
    assert seen["system"] == "HARNESS"
    assert isinstance(out["structured_response"], TriageResult)


def test_count_tool_calls_ignores_structured_output_tool():
    msgs = [AIMessage(content="", tool_calls=[{"name": "get_record_section", "args": {}, "id": "a"},
                                              {"name": "get_record_section", "args": {}, "id": "b"}]),
            AIMessage(content="", tool_calls=[{"name": "TriageResult", "args": {}, "id": "c"}])]
    assert td.count_tool_calls(msgs) == 2
