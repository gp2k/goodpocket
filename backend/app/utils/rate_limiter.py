"""
Simple in-memory rate limiter.
For production, consider using Redis for distributed rate limiting.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List
from uuid import UUID

from fastapi import HTTPException, status
import structlog

from app.config import get_settings

logger = structlog.get_logger()

# In-memory storage for rate limiting
# Format: {user_id: [(timestamp, action), ...]}
_rate_limit_store: Dict[str, List[datetime]] = defaultdict(list)


def _cleanup_old_entries(key: str, window: timedelta) -> None:
    """Remove entries older than the window."""
    cutoff = datetime.utcnow() - window
    _rate_limit_store[key] = [
        ts for ts in _rate_limit_store[key]
        if ts > cutoff
    ]


async def check_rate_limit(
    user_id: UUID,
    action: str,
) -> None:
    """
    Check if an action is within rate limits.
    
    Args:
        user_id: User performing the action
        action: Type of action (e.g., "saves")
        
    Raises:
        HTTPException: If rate limit exceeded
    """
    settings = get_settings()
    
    # Different limits for different actions
    if action == "saves":
        limit = settings.rate_limit_saves_per_hour
        window = timedelta(hours=1)
    else:
        limit = settings.rate_limit_requests_per_minute
        window = timedelta(minutes=1)
    
    key = f"{user_id}:{action}"
    
    # Clean up old entries
    _cleanup_old_entries(key, window)
    
    # Check current count
    current_count = len(_rate_limit_store[key])
    
    if current_count >= limit:
        logger.warning(
            "Rate limit exceeded",
            user_id=str(user_id),
            action=action,
            count=current_count,
            limit=limit,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {limit} {action} per {'hour' if action == 'saves' else 'minute'}.",
        )
    
    # Record this action
    _rate_limit_store[key].append(datetime.utcnow())


async def check_ip_rate_limit(
    ip_address: str,
    limit: int = 100,
    window_minutes: int = 1,
) -> None:
    """
    Check IP-based rate limit.
    
    Args:
        ip_address: Client IP address
        limit: Maximum requests in window
        window_minutes: Time window in minutes
        
    Raises:
        HTTPException: If rate limit exceeded
    """
    key = f"ip:{ip_address}"
    window = timedelta(minutes=window_minutes)
    
    _cleanup_old_entries(key, window)
    
    current_count = len(_rate_limit_store[key])
    
    if current_count >= limit:
        logger.warning(
            "IP rate limit exceeded",
            ip=ip_address,
            count=current_count,
            limit=limit,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )
    
    _rate_limit_store[key].append(datetime.utcnow())


def reset_rate_limits() -> None:
    """Reset all rate limits (for testing)."""
    global _rate_limit_store
    _rate_limit_store = defaultdict(list)
