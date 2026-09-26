from harness.adapters.llm.openrouter import strict_schema
from harness.evolution.investigator import Findings
from harness.evolution.proposer import Drafts


def _objects(node):
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node:
            yield node
        for v in node.values():
            yield from _objects(v)
    elif isinstance(node, list):
        for v in node:
            yield from _objects(v)


def test_strict_schema_keeps_fields_named_title_and_requires_all():
    for model in (Drafts, Findings):
        schema = strict_schema(model)
        for obj in _objects(schema):
            assert obj["additionalProperties"] is False
            assert sorted(obj["required"]) == sorted(obj["properties"])
    draft = strict_schema(Drafts)["$defs"]["Draft"]
    assert "title" in draft["properties"]
