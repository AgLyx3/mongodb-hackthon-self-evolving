"""Read-only API for the FDE review UI. Transport only: validate, delegate, return."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from harness.adapters.mongo import views
from harness.datagen.registry import is_known

app = FastAPI(title="Self-evolving FDE harness")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["GET"], allow_headers=["*"])
def _check(customer: str) -> None:
    if not is_known(customer):
        raise HTTPException(status_code=404, detail="unknown customer")


@app.get("/api/customers")
async def list_customers() -> list[dict[str, Any]]:
    return await views.customers()


@app.get("/api/customers/{customer}/timeline")
async def timeline(customer: str) -> dict[str, Any]:
    _check(customer)
    return await views.timeline(customer)


@app.get("/api/customers/{customer}/harness")
async def harness(customer: str, version: str | None = None) -> dict[str, Any]:
    _check(customer)
    if version is not None and not version.isalnum():
        raise HTTPException(status_code=400, detail="bad version")
    return await views.harness(customer, version)


@app.get("/api/customers/{customer}/proposals")
async def proposals(customer: str) -> list[dict[str, Any]]:
    _check(customer)
    return await views.proposals(customer)


@app.get("/api/customers/{customer}/sources")
async def sources(customer: str) -> dict[str, Any]:
    _check(customer)
    return await views.sources(customer)


@app.get("/api/customers/{customer}/metrics")
async def metrics(customer: str) -> dict[str, Any]:
    _check(customer)
    return await views.metrics(customer)


@app.get("/api/customers/{customer}/comparison")
async def comparison(customer: str) -> dict[str, Any]:
    _check(customer)
    return await views.comparison(customer)


@app.get("/api/customers/{customer}/probes")
async def probes(customer: str) -> list[dict[str, Any]]:
    _check(customer)
    return await views.probes(customer)


@app.get("/api/customers/{customer}/ladder")
async def ladder(customer: str) -> list[dict[str, Any]]:
    _check(customer)
    return await views.ladder(customer)
