"""
Integration tests for snapshot API endpoints.
"""

import pytest


@pytest.mark.integration
class TestSnapshotAPI:
    """Integration tests for snapshot API."""

    def test_snapshot_crud_flow(self, test_client, sample_target):
        """
        Test complete snapshot CRUD flow.

        Tests:
        1. Create a new snapshot for a target
        2. List snapshots for the target
        3. Get snapshot by ID
        4. Update snapshot
        5. Get snapshot stats
        6. Delete snapshot
        """
        # 1. Create snapshot
        create_response = test_client.post(
            "/api/v1/snapshots",
            json={
                "target_id": sample_target.id,
                "name": "v1.0",
                "description": "Initial snapshot"
            }
        )

        assert create_response.status_code == 201
        snapshot_data = create_response.json()
        assert snapshot_data["name"] == "v1.0"
        assert snapshot_data["target_id"] == sample_target.id
        snapshot_id = snapshot_data["id"]

        # 2. List snapshots for target
        list_response = test_client.get(
            f"/api/v1/targets/{sample_target.id}/snapshots"
        )

        assert list_response.status_code == 200
        snapshots = list_response.json()
        assert len(snapshots) == 1
        assert snapshots[0]["name"] == "v1.0"

        # 3. Get snapshot by ID
        get_response = test_client.get(f"/api/v1/snapshots/{snapshot_id}")

        assert get_response.status_code == 200
        assert get_response.json()["id"] == snapshot_id

        # 4. Update snapshot
        update_response = test_client.put(
            f"/api/v1/snapshots/{snapshot_id}",
            json={"name": "v1.1", "description": "Updated"}
        )

        assert update_response.status_code == 200
        assert update_response.json()["name"] == "v1.1"

        # 5. Get snapshot stats
        stats_response = test_client.get(f"/api/v1/snapshots/{snapshot_id}/stats")

        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats["snapshot_id"] == snapshot_id
        assert "total_answers" in stats

        # 6. Delete snapshot
        delete_response = test_client.delete(f"/api/v1/snapshots/{snapshot_id}")

        assert delete_response.status_code == 204

        # Verify deleted
        get_deleted = test_client.get(f"/api/v1/snapshots/{snapshot_id}")
        assert get_deleted.status_code == 404

    def test_get_snapshot_not_found(self, test_client):
        """Test error handling when snapshot doesn't exist."""
        response = test_client.get("/api/v1/snapshots/99999")

        assert response.status_code == 404

    def test_update_snapshot_not_found(self, test_client):
        """Test error handling when updating non-existent snapshot."""
        response = test_client.put(
            "/api/v1/snapshots/99999",
            json={"name": "New Name"}
        )

        assert response.status_code == 404

    def test_delete_snapshot_not_found(self, test_client):
        """Test error handling when deleting non-existent snapshot."""
        response = test_client.delete("/api/v1/snapshots/99999")

        assert response.status_code == 404
