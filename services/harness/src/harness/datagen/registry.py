"""Customer registry. Held-out customers are modules under datagen/heldout/,
written by a separate agent; the builder imports them but does not read them.

A customer module must expose:
    build() -> harness.datagen.spec.Customer
    classify(record) -> (case_type, disposition)      # ground truth
    naive_base(record) -> disposition                 # base harness read literally
optional:
    presentation_rubric(proposal: dict) -> (ok: bool, reason_tag: str, note: str)
"""

from __future__ import annotations

import importlib
from types import ModuleType

BUILTIN = {"bank": "harness.datagen.bank", "fintech": "harness.datagen.fintech"}
HELDOUT_PREFIX = "heldout_"


def is_known(customer: str) -> bool:
    return customer in BUILTIN or (
        customer.startswith(HELDOUT_PREFIX) and customer.replace("_", "").isalnum())


def module_for(customer: str) -> ModuleType:
    if customer in BUILTIN:
        return importlib.import_module(BUILTIN[customer])
    if not is_known(customer):
        raise KeyError(f"unknown customer {customer!r}")
    return importlib.import_module(f"harness.datagen.heldout.{customer}")
