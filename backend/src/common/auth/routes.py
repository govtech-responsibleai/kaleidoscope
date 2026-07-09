"""Auth routes for login and user management."""

import logging
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordRequestForm
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.id_token import verify_oauth2_token
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.common.config import get_settings
from src.common.database.connection import get_db
from src.common.database.repositories.user_repo import UserRepository
from src.common.auth.utils import verify_password, create_access_token, hash_password
from src.common.auth.dependencies import require_admin
from src.common.auth.demo_target_seed import seed_demo_target

logger = logging.getLogger(__name__)

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


class GoogleLoginRequest(BaseModel):
    """Request model for Google Sign-In."""
    credential: str


class SignupRequest(BaseModel):
    """Request model for whitelist-gated self-signup."""
    email: str
    password: str


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


def _allowed_domains() -> set[str]:
    """Return configured allowed email domains, normalized for exact matching."""
    return {
        domain.strip().lower()
        for domain in settings.allowed_email_domains.split(",")
        if domain.strip()
    }


def _email_domain(email: str) -> str:
    """Extract a lower-case email domain."""
    return email.rsplit("@", 1)[-1].lower() if "@" in email else ""


def _signup_whitelist() -> Optional[set[str]]:
    """Load the self-signup email whitelist, read fresh on each call.

    The whitelist is a plain-text file (one email per line) at
    ``settings.signup_whitelist_path``. Blank lines and lines starting with
    ``#`` are ignored, and emails are normalized to lower case for
    case-insensitive matching.

    Returns:
        A set of allowed lower-case emails, or ``None`` if the file is missing
        or unreadable (signalling that self-registration is not configured).
    """
    path = Path(settings.signup_whitelist_path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        logger.warning(
            "Signup whitelist not found or unreadable at %s; self-registration is disabled",
            settings.signup_whitelist_path,
        )
        return None

    emails: set[str] = set()
    for line in raw.splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        emails.add(entry.lower())
    return emails


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


@router.post("/google", response_model=TokenResponse)
def google_login(
    request: GoogleLoginRequest,
    db: Session = Depends(get_db),
):
    """Login or register with a verified Google ID token."""
    allowed_domains = _allowed_domains()
    if not allowed_domains:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access is restricted to authorised email domains.",
        )
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google Sign-In is not configured.",
        )

    try:
        claims = verify_oauth2_token(
            request.credential,
            GoogleRequest(),
            settings.google_client_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        ) from exc

    email = str(claims.get("email", "")).strip().lower()
    if not email or claims.get("email_verified") is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        )

    domain = _email_domain(email)
    if domain not in allowed_domains:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access is restricted to authorised email domains.",
        )

    user = UserRepository.get_by_username(db, email)
    if not user:
        user = UserRepository.create(db, email, None, is_admin=False)
        seed_demo_target(db, int(user.id))  # type: ignore[arg-type]

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


@router.post("/signup", response_model=TokenResponse)
def signup(
    request: SignupRequest,
    db: Session = Depends(get_db),
):
    """Self-register a non-admin account if the email is whitelisted.

    Whitelisted users are created with a hashed password, receive the
    configured demo target, and are logged in immediately (JWT returned),
    mirroring the account an admin would otherwise create for them.

    Args:
        request: Signup payload with email and password.
        db: Database session.

    Returns:
        A token response with the issued JWT.

    Raises:
        HTTPException: 403 if self-registration is disabled or the email is not
            whitelisted; 400 if an account with the email already exists.
    """
    email = request.email.strip().lower()

    whitelist = _signup_whitelist()
    if whitelist is None:
        # File missing/unreadable: fail closed. The distinct warning is logged
        # by _signup_whitelist(); the user sees a generic restriction message.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-registration is not available.",
        )
    if email not in whitelist:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This email has not been invited to sign up.",
        )

    if UserRepository.get_by_username(db, email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    user = UserRepository.create(db, email, hash_password(request.password), is_admin=False)
    seed_demo_target(db, int(user.id))  # type: ignore[arg-type]

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
    seed_demo_target(db, int(user.id))  # type: ignore[arg-type]
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
    seed_demo_target(db, int(user.id))  # type: ignore[arg-type]
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
