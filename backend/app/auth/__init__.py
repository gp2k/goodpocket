"""Authentication module for Supabase JWT validation."""
from app.auth.dependencies import get_current_user, CurrentUser

__all__ = ["get_current_user", "CurrentUser"]
