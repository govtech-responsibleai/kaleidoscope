"""Auth routes for login and user management."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.common.config import get_settings
from src.common.database.connection import get_db
from src.common.database.repositories.user_repo import UserRepository
from src.common.auth.utils import verify_password, create_access_token, hash_password
from src.common.auth.dependencies import require_admin

router = APIRouter()
settings = get_settings()


class TokenResponse(BaseModel):
    """Response model for login."""
    access_token: str
    token_type: str = "bearer"
    is_admin: bool = False
    username: str = ""


class CreateUserRequest(BaseModel):
    """Request model for creating a user."""
    username: str
    password: str
    is_admin: bool = False


class CreateUserResponse(BaseModel):
    """Response model for user creation."""
    message: str
    username: str


class UserResponse(BaseModel):
    """Response model for user listing."""
    id: int
    username: str
    is_active: bool
    is_admin: bool
    created_at: str
    target_count: int



@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login with username and password.

    Args:
        form_data: OAuth2 form with username and password.
        db: Database session.

    Returns:
        Access token with user metadata.
    """
    user = UserRepository.get_by_username(db, form_data.username)

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
        )

    access_token = create_access_token(user.id)
    return TokenResponse(
        access_token=access_token,
        is_admin=user.is_admin,
        username=user.username,
    )


@router.post("/admin/create-user", response_model=CreateUserResponse)
def create_user(
    request: CreateUserRequest,
    x_admin_key: str = Header(..., description="Admin secret key"),
    db: Session = Depends(get_db),
):
    """Create a new user (admin only, X-Admin-Key auth)."""
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key"
        )

    if UserRepository.get_by_username(db, request.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    user = UserRepository.create(db, request.username, hash_password(request.password), request.is_admin)
    return CreateUserResponse(
        message=f"User '{user.username}' created successfully{' (admin)' if request.is_admin else ''}",
        username=user.username
    )


@router.post("/admin/create-user-jwt", response_model=CreateUserResponse)
def create_user_jwt(
    request: CreateUserRequest,
    admin_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new user via JWT admin auth (for frontend use)."""
    if UserRepository.get_by_username(db, request.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    user = UserRepository.create(db, request.username, hash_password(request.password), request.is_admin)
    return CreateUserResponse(
        message=f"User '{user.username}' created successfully{' (admin)' if request.is_admin else ''}",
        username=user.username
    )


@router.delete("/admin/delete-user/{username}")
def delete_user(
    username: str,
    x_admin_key: str = Header(..., description="Admin API key"),
    db: Session = Depends(get_db),
):
    """Delete a user (admin only via X-Admin-Key)."""
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key"
        )

    user = UserRepository.get_by_username(db, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    db.delete(user)
    db.commit()
    return {"message": f"User '{username}' deleted successfully"}


@router.delete("/admin/delete-user-jwt/{username}")
def delete_user_jwt(
    username: str,
    admin_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a user via JWT admin auth (for frontend use)."""
    user = UserRepository.get_by_username(db, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    db.delete(user)
    db.commit()
    return {"message": f"User '{username}' deleted successfully"}


@router.get("/admin/users", response_model=List[UserResponse])
def list_users(
    admin_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all users with target counts (admin only, JWT auth).

    Args:
        admin_user: Authenticated admin user.
        db: Database session.

    Returns:
        List of users with target counts.
    """
    users = UserRepository.get_all_with_target_counts(db)
    return [
        UserResponse(
            id=u["id"],
            username=u["username"],
            is_active=u["is_active"],
            is_admin=u["is_admin"],
            created_at=str(u["created_at"]),
            target_count=u["target_count"],
        )
        for u in users
    ]
