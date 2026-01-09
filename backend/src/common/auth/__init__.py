"""Auth module for user authentication."""

from src.common.auth.dependencies import get_current_user
from src.common.auth.routes import router as auth_router

__all__ = ["get_current_user", "auth_router"]
