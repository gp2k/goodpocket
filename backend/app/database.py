"""
Database connection management using asyncpg.
Provides connection pooling and query helpers.
"""
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any, Optional
import asyncpg
from pgvector.asyncpg import register_vector
import structlog

from app.config import get_settings

logger = structlog.get_logger()

# Global connection pool
_pool: Optional[asyncpg.Pool] = None


async def init_db() -> None:
    """Initialize database connection pool."""
    global _pool
    settings = get_settings()
    
    logger.info("Initializing database connection pool")
    
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=10,
        command_timeout=60,
        init=_init_connection,
        statement_cache_size=0,  # Required for Supabase transaction pooler (pgbouncer)
    )
    
    logger.info("Database connection pool initialized")


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Initialize each connection with pgvector support."""
    await register_vector(conn)


async def close_db() -> None:
    """Close database connection pool."""
    global _pool
    if _pool:
        logger.info("Closing database connection pool")
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    """Get the connection pool. Raises if not initialized."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db() first.")
    return _pool


@asynccontextmanager
async def get_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Get a database connection from the pool."""
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn


async def execute(query: str, *args: Any) -> str:
    """Execute a query and return status."""
    async with get_connection() as conn:
        return await conn.execute(query, *args)


async def fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    """Execute a query and return all rows."""
    async with get_connection() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args: Any) -> Optional[asyncpg.Record]:
    """Execute a query and return a single row."""
    async with get_connection() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args: Any) -> Any:
    """Execute a query and return a single value."""
    async with get_connection() as conn:
        return await conn.fetchval(query, *args)
