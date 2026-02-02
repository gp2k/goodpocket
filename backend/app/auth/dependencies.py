"""
Authentication dependencies for FastAPI.
Validates Supabase JWT tokens and extracts user information.
"""
from typing import Annotated, Optional
from uuid import UUID
import httpx

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt, jwk
from pydantic import BaseModel
import structlog

from app.config import get_settings

logger = structlog.get_logger()

# HTTP Bearer token scheme
security = HTTPBearer()

# Cache for JWKS
_jwks_cache: dict = {}


class CurrentUser(BaseModel):
    """Authenticated user information extracted from JWT."""
    id: UUID
    email: Optional[str] = None
    
    class Config:
        frozen = True


def get_jwks(supabase_url: str) -> dict:
    """Fetch JWKS from Supabase."""
    global _jwks_cache
    
    if _jwks_cache:
        return _jwks_cache
    
    jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
    try:
        response = httpx.get(jwks_url, timeout=10)
        response.raise_for_status()
        _jwks_cache = response.json()
        logger.info("JWKS fetched successfully", url=jwks_url)
        return _jwks_cache
    except Exception as e:
        logger.error("Failed to fetch JWKS", error=str(e), url=jwks_url)
        return {}


def decode_jwt(token: str) -> dict:
    """
    Decode and validate a Supabase JWT token.
    
    Args:
        token: The JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    settings = get_settings()
    
    try:
        # Get token header to check algorithm
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
        kid = header.get("kid")
        logger.info("JWT token header", algorithm=alg, kid=kid)
        
        if alg == "ES256":
            # Use JWKS for ES256
            jwks = get_jwks(settings.supabase_url)
            if not jwks or "keys" not in jwks:
                raise JWTError("Failed to fetch JWKS")
            
            # Find the key with matching kid
            key = None
            for k in jwks["keys"]:
                if k.get("kid") == kid:
                    key = k
                    break
            
            if not key:
                # Use first key if kid not found
                key = jwks["keys"][0] if jwks["keys"] else None
            
            if not key:
                raise JWTError("No matching key found in JWKS")
            
            payload = jwt.decode(
                token,
                key,
                algorithms=["ES256"],
                options={"verify_aud": False}
            )
        else:
            # Use HS256 with symmetric key
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False}
            )
        
        return payload
    except JWTError as e:
        logger.warning("JWT validation failed", error=str(e), token_preview=token[:50] if token else None)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
) -> CurrentUser:
    """
    FastAPI dependency that extracts the current user from JWT.
    
    Usage:
        @router.get("/protected")
        async def protected_route(user: CurrentUser = Depends(get_current_user)):
            return {"user_id": user.id}
    """
    token = credentials.credentials
    payload = decode_jwt(token)
    
    # Extract user info from Supabase JWT
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user ID",
        )
    
    email = payload.get("email")
    
    return CurrentUser(id=UUID(user_id), email=email)
