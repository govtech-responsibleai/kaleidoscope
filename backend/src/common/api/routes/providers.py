"""API routes for provider setup and merged setup state."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from src.common.auth import get_current_user_id
from src.common.database.connection import get_db
from src.common.llm.provider_service import (
    build_provider_catalog_response,
    build_provider_setup_response,
    delete_provider_credentials,
    delete_service_credentials,
    store_provider_credentials,
    store_service_credentials,
)
from src.common.models.provider_setup import (
    ProviderCatalogResponse,
    ProviderCredentialUpsertRequest,
    ProviderSetupResponse,
    ServiceCredentialUpsertRequest,
)

router = APIRouter()


@router.get("/providers/catalog", response_model=ProviderCatalogResponse)
def get_provider_catalog(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProviderCatalogResponse:
    """Return provider metadata with merged credential-state visibility."""
    return build_provider_catalog_response(db, user_id)


@router.get("/providers/setup", response_model=ProviderSetupResponse)
def get_provider_setup(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProviderSetupResponse:
    """Return the effective provider setup state for the current user."""
    return build_provider_setup_response(db, user_id)


@router.put("/providers/{provider_key}", status_code=status.HTTP_204_NO_CONTENT)
def upsert_provider_credentials(
    provider_key: str,
    payload: ProviderCredentialUpsertRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> Response:
    """Save one personal provider credential set."""
    try:
        store_provider_credentials(db, user_id, provider_key, payload.credentials)
        db.commit()
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/providers/{provider_key}", status_code=status.HTTP_204_NO_CONTENT)
def remove_provider_credentials(
    provider_key: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> Response:
    """Delete one personal provider credential set."""
    try:
        delete_provider_credentials(db, user_id, provider_key)
        db.commit()
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/providers/services/{service_key}", status_code=status.HTTP_204_NO_CONTENT)
def upsert_service_credentials(
    service_key: str,
    payload: ServiceCredentialUpsertRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> Response:
    """Save one personal service credential set."""
    try:
        store_service_credentials(db, user_id, service_key, payload.credentials)
        db.commit()
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/providers/services/{service_key}", status_code=status.HTTP_204_NO_CONTENT)
def remove_service_credentials(
    service_key: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> Response:
    """Delete one personal service credential set."""
    try:
        delete_service_credentials(db, user_id, service_key)
        db.commit()
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
