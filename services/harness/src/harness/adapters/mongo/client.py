"""Async MongoDB clients. One per credential, built once and reused.

Two credentials exist on purpose (decision 1 / kernel invariant): the app user
can write the kernel collections; the proposer user can only read and insert
into `proposals`. Evolution code that proposes changes must use `proposer_db()`.
"""

from functools import lru_cache

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from harness.config import get_settings


@lru_cache
def _app_client() -> AsyncMongoClient:
    s = get_settings()
    return AsyncMongoClient(s.mongodb_uri_app.get_secret_value(), appname="fde-harness")


@lru_cache
def _proposer_client() -> AsyncMongoClient:
    s = get_settings()
    return AsyncMongoClient(s.mongodb_uri_proposer.get_secret_value(), appname="fde-proposer")


def app_db() -> AsyncDatabase:
    return _app_client()[get_settings().mongodb_db]


def eval_db() -> AsyncDatabase:
    """Answer key, labels, oracle answers. Only the app user can read it; the
    proposer user has no role on this database."""
    return _app_client()["fde_eval"]


def proposer_db() -> AsyncDatabase:
    return _proposer_client()[get_settings().mongodb_db]
