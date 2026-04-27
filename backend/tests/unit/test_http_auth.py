"""Unit tests for managed HTTP auth resolution."""

from types import SimpleNamespace

import pytest

from src.common.connectors.http_auth import encrypt_http_auth_secret
from src.common.connectors.registry import get_connector
from src.common.database.models import Target
from src.common.database.repositories import TargetHttpAuthSecretRepository


@pytest.mark.unit
class TestManagedHttpAuth:
    def test_get_connector_resolves_transient_managed_auth(self):
        target = SimpleNamespace(
            id="probe",
            endpoint_type="http",
            api_endpoint="https://api.example.com",
            endpoint_config={
                "response_content_path": "output",
                "auth": {
                    "preset": "x-api-key",
                    "secret_value": "sk-live-1234",
                },
            },
        )

        connector = get_connector(target)

        assert connector.config["headers"]["x-api-key"] == "sk-live-1234"
        assert "auth" not in connector.config

    def test_get_connector_resolves_saved_managed_auth(self, test_db):
        target = Target(
            name="Managed auth bot",
            api_endpoint="https://api.example.com",
            endpoint_type="http",
            endpoint_config={
                "response_content_path": "output",
                "auth": {
                    "preset": "bearer",
                    "masked_value": "••••1234",
                    "is_configured": True,
                },
            },
        )
        test_db.add(target)
        test_db.commit()
        test_db.refresh(target)

        TargetHttpAuthSecretRepository.upsert(
            test_db,
            target.id,
            encrypt_http_auth_secret("sk-secret-1234"),
        )
        test_db.commit()

        connector = get_connector(target, db=test_db)

        assert connector.config["headers"]["Authorization"] == "Bearer sk-secret-1234"
        assert "auth" not in connector.config

    def test_get_connector_missing_saved_secret_fails_clearly(self, test_db):
        target = Target(
            name="Broken auth bot",
            api_endpoint="https://api.example.com",
            endpoint_type="http",
            endpoint_config={
                "response_content_path": "output",
                "auth": {
                    "preset": "bearer",
                    "masked_value": "••••1234",
                    "is_configured": True,
                },
            },
        )
        test_db.add(target)
        test_db.commit()
        test_db.refresh(target)

        with pytest.raises(ValueError, match="no saved secret was found"):
            get_connector(target, db=test_db)
