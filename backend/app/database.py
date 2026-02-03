"""
Database connection management using asyncpg.
Provides connection pooling and query helpers.
"""
import asyncio
import ipaddress
import re
import socket
from urllib.parse import urlparse, urlunparse
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any, Optional
import asyncpg
from pgvector.asyncpg import register_vector
import structlog

from app.config import get_settings

logger = structlog.get_logger()

# Global connection pool
_pool: Optional[asyncpg.Pool] = None


def _resolve_host_to_ipv4_sync(host: str, port: int) -> str:
    """Resolve hostname to IPv4. Returns host unchanged if already IPv4 or resolution fails."""
    if not host:
        return host
    try:
        ipaddress.IPv4Address(host)
        return host  # already IPv4
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        if infos:
            return infos[0][4][0]
    except (socket.gaierror, OSError):
        pass
    return host


def _dsn_use_ipv4_host(dsn: str) -> str:
    """
    Replace hostname in DSN with its IPv4 address.
    Railway does not support outbound IPv6; Supabase direct connection often uses IPv6,
    causing OSError [Errno 101] Network is unreachable. Forcing IPv4 fixes this.
    """
    parsed = urlparse(dsn)
    host = parsed.hostname
    port = parsed.port or 5432
    if not host:
        return dsn
    ipv4 = _resolve_host_to_ipv4_sync(host, port)
    if ipv4 == host:
        return dsn
    # Rebuild netloc without re-encoding userinfo (password may contain : or @)
    netloc = parsed.netloc
    at = netloc.rfind("@")
    if at >= 0:
        userinfo = netloc[: at + 1]
        hostport = netloc[at + 1 :]
    else:
        userinfo = ""
        hostport = netloc
    if ":" in hostport:
        _, _, port_str = hostport.rpartition(":")
        new_netloc = f"{userinfo}{ipv4}:{port_str}"
    else:
        new_netloc = f"{userinfo}{ipv4}"
    return urlunparse((parsed.scheme, new_netloc, parsed.path or "", parsed.params, parsed.query, parsed.fragment))


def _normalize_database_url(url: str) -> str:
    """
    Remove brackets around hostname when it is not an IPv6 address.
    Python's urllib treats [host] as IPv6 literal and validates it; Supabase/Railway
    sometimes provide DATABASE_URL with bracketed hostname (e.g. @[db.xxx.supabase.co]:5432),
    which causes ValueError. We strip brackets for hostnames so asyncpg/urllib accept the DSN.
    """
    # Handle percent-encoded brackets (e.g. from some env sources)
    url = url.replace("%5B", "[").replace("%5D", "]")

    def _strip_brackets(m: re.Match[str]) -> str:
        host = m.group(1)
        try:
            ipaddress.ip_address(host)
            return m.group(0)  # valid IPv4/IPv6, keep brackets
        except ValueError:
            return "@" + host  # hostname: remove brackets

    return re.sub(r"@\[([^\]]+)\]", _strip_brackets, url)


async def init_db() -> None:
    """Initialize database connection pool."""
    global _pool
    settings = get_settings()

    logger.info("Initializing database connection pool")

    dsn = _normalize_database_url(settings.database_url)
    # Railway 등 IPv6 아웃바운드가 없는 환경에서 Supabase 연결 시 Network unreachable 방지
    loop = asyncio.get_event_loop()
    dsn = await loop.run_in_executor(None, _dsn_use_ipv4_host, dsn)

    _pool = await asyncpg.create_pool(
        dsn=dsn,
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
