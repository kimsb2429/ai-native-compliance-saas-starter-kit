"""One connection pool, tenant set per transaction (B14, kit form).

The engagement kept a dictionary of pools keyed by infrastructure prefix and
relied on application code to scope every query. The kit keeps ONE pool and
lets Postgres enforce the tenant line: every tenant-scoped transaction starts
with set_config('app.org_id', <uuid>, true) and the RLS policies in
db/schema.sql do the rest. The 'true' makes the setting transaction-local, so
a connection returned to the pool carries nothing over.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from agent import settings

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.database_url(),
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row, "autocommit": False},
            # Serverless Postgres suspends when idle and drops the sockets a warm
            # pool is holding. Validate every connection on checkout and retire
            # idle ones early, so a resumed database never sees a dead socket.
            check=ConnectionPool.check_connection,
            max_idle=60,
            reconnect_timeout=30,
            open=True,
        )
        logger.info("db pool opened (min 1, max 10)")
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def _connection_with_retry():
    """Check out a connection; if the first checkout fails on a dead socket, try once more."""
    try:
        return pool().connection()
    except psycopg.OperationalError:
        logger.warning("connection checkout failed once; retrying")
        return pool().connection()


@contextmanager
def tenant_txn(org_id: UUID) -> Iterator[psycopg.Cursor]:
    """A transaction in which RLS sees exactly one tenant."""
    with _connection_with_retry() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("select set_config('app.org_id', %s, true)", (str(org_id),))
                yield cur


@contextmanager
def platform_txn() -> Iterator[psycopg.Cursor]:
    """A transaction for the shared platform tables (no tenant setting)."""
    with _connection_with_retry() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                yield cur
