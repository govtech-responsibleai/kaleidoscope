"""Auth routes for login and user management."""

from fastapi import APIRouter, Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.common.config import get_settings
from src.common.database.connection import get_db
from src.common.database.repositories.user_repo import UserRepository
from src.common.auth.utils import verify_password, create_access_token, hash_password

router = APIRouter()
settings = get_settings()


class TokenResponse(BaseModel):
    """Response model for login."""
    access_token: str
    token_type: str = "bearer"


class CreateUserRequest(BaseModel):
    """Request model for creating a user."""
    username: str
    password: str


class CreateUserResponse(BaseModel):
    """Response model for user creation."""
    message: str
    username: str


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login with username and password.

    Args:
        form_data: OAuth2 form with username and password
        db: Database session

    Returns:
        Access token
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
    return TokenResponse(access_token=access_token)


@router.post("/admin/create-user", response_model=CreateUserResponse)
def create_user(
    request: CreateUserRequest,
    x_admin_key: str = Header(..., description="Admin secret key"),
    db: Session = Depends(get_db)
):
    """
    Create a new user (admin only).

    Requires X-Admin-Key header with the admin secret key.
    """
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

    user = UserRepository.create(db, request.username, hash_password(request.password))
    return CreateUserResponse(
        message=f"User '{user.username}' created successfully",
        username=user.username
    )


@router.delete("/admin/delete-user/{username}")
def delete_user(
    username: str,
    x_admin_key: str = Header(..., description="Admin API key"),
    db: Session = Depends(get_db)
):
    """
    Delete a user (admin only).

    Requires X-Admin-Key header with the admin API key.
    """
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
