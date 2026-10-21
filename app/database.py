import ssl
from pathlib import Path
from typing import Sequence, Any

import aiomysql

from app.config import settings

_pool: aiomysql.Pool | None = None


def _build_ssl_context() -> ssl.SSLContext | None:
    if not settings.db_ssl:
        return None

    ctx = ssl.create_default_context(cafile=settings.db_ssl_ca or None)

    if settings.db_ssl_ca:
        ca_path = Path(settings.db_ssl_ca)
        if not ca_path.exists():
            raise RuntimeError(f"CA bundle not found at {ca_path.resolve()}")
        ctx.load_verify_locations(cafile=str(ca_path))

    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


async def init_pool() -> None:
    global _pool
    _pool = await aiomysql.create_pool(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        db=settings.db_name,
        autocommit=True,
        minsize=1,
        maxsize=10,
        charset="utf8mb4",
        ssl=_build_ssl_context(),
        cursorclass=aiomysql.DictCursor,
    )


async def close_pool() -> None:
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None


async def call_procedure(name: str, args: Sequence[Any] = ()) -> list[list[dict]]:
    """Executes CALL name(...) and returns every result set as a list of dict rows."""
    assert _pool is not None, "DB pool not initialized"
    placeholders = ",".join(["%s"] * len(args))
    sql = f"CALL {name}({placeholders})" if args else f"CALL {name}()"

    results: list[list[dict]] = []
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, args)
            while True:
                if cur.description:
                    rows = await cur.fetchall()
                    results.append(list(rows))
                else:
                    results.append([])
                if not await cur.nextset():
                    break
    return results


async def call_procedure_one(name: str, args: Sequence[Any] = ()) -> list[dict]:
    """Convenience: returns only the first result set."""
    sets = await call_procedure(name, args)
    return sets[0] if sets else []


async def fetch_one(sql: str, args: Sequence[Any] = ()) -> dict | None:
    """Runs a raw SELECT and returns the first row (or None). Used for queries
    that have no stored procedure, e.g. looking up id_vehiculo from demos."""
    assert _pool is not None, "DB pool not initialized"
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, args)
            return await cur.fetchone()