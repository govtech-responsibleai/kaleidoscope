"""Auth module for user authentication."""

from src.common.auth.dependencies import (
    get_current_user,
    get_current_user_id,
    get_scoped_db,
    require_admin,
)
from src.common.auth.routes import router as auth_router

__all__ = [
    "get_current_user",
    "get_current_user_id",
    "get_scoped_db",
    "require_admin",
    "auth_router",
]
