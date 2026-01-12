"""Auth dependencies for route protection."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy import event, or_
from sqlalchemy.orm import Session, with_loader_criteria

from src.common.config import get_settings
from src.common.database.connection import get_db
from src.common.database.repositories.user_repo import UserRepository
from src.common.database.models import User, Target, Judge

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user from the JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = UserRepository.get_by_id(db, int(user_id))
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def get_current_user_id(user: User = Depends(get_current_user)) -> int:
    """Get just the current user's ID."""
    return user.id


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require the current user to be an admin."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


def get_scoped_db(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Session:
    """
    Get a database session with automatic user-scoping.

    For non-admin users, automatically filters Target and Judge queries
    to only return records owned by the current user.

    Admin users see all records.
    """
    # Store user info on session for the event listener to access
    db.info["current_user_id"] = user.id
    db.info["current_user_is_admin"] = user.is_admin
    return db


def _apply_user_filter(execute_state):
    """
    SQLAlchemy event listener that applies user filtering to queries.

    This automatically adds user-scoping to queries on Target and Judge tables:
    - Targets: only show records where user_id matches current user
    - Judges: show records where user_id matches current user OR user_id is NULL (global/baseline)

    Admin users see all records.
    """
    session = execute_state.session

    # Get user info from session
    user_id = session.info.get("current_user_id")
    is_admin = session.info.get("current_user_is_admin", False)

    # Skip filtering if no user in context or user is admin
    if user_id is None or is_admin:
        return

    # Only filter SELECT queries
    if not execute_state.is_select:
        return

    # Apply filter criteria
    # Targets: strict user ownership
    # Judges: user's own OR global (user_id is NULL for baseline judges)
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(Target, Target.user_id == user_id, include_aliases=True),
        with_loader_criteria(
            Judge,
            or_(Judge.user_id == user_id, Judge.user_id.is_(None)),
            include_aliases=True
        ),
    )


# Register the event listener on the Session class
event.listen(Session, "do_orm_execute", _apply_user_filter)
