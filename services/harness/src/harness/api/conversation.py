"""Conversation view route. Transport only: validate, delegate, return."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from harness.adapters.mongo.conversation import conversation as load_conversation
from harness.datagen.registry import is_known

router = APIRouter()


@router.get("/api/customers/{customer}/conversation")
async def conversation(customer: str) -> dict[str, Any]:
    if not is_known(customer):
        raise HTTPException(status_code=404, detail="unknown customer")
    return await load_conversation(customer)
