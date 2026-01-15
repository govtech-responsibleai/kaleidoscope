"""
Integration tests for user data scoping.

Tests that users can only see their own data, while admins can see all data.
"""

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.models import Target, Judge, User, JudgeTypeEnum
from src.common.auth import auth_router, get_scoped_db, get_current_user_id
from src.common.auth.utils import create_access_token
from src.common.config import get_settings
from src.query_generation.api.routes import targets
from src.scoring.api.routes import judges
from tests.conftest import get_test_password_hash

settings = get_settings()


@pytest.fixture
def scoping_test_app(test_db_factory):
    """Create a test app configured for data scoping tests."""
    test_app = FastAPI()

    # Auth router (public)
    test_app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])

    # Protected routes with scoping
    test_app.include_router(
        targets.router,
        prefix="/api/v1/targets",
        tags=["Targets"],
        dependencies=[Depends(get_scoped_db)]
    )
    test_app.include_router(
        judges.router,
        prefix="/api/v1",
        tags=["Judges"],
        dependencies=[Depends(get_scoped_db)]
    )

    # Override database dependency
    def override_get_db():
        db = test_db_factory()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db

    return test_app


@pytest.fixture
def user_a(test_db):
    """Create User A for scoping tests."""
    user = User(
        username="user_a",
        hashed_password=get_test_password_hash("password_a"),
        is_active=True,
        is_admin=False
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def user_b(test_db):
    """Create User B for scoping tests."""
    user = User(
        username="user_b",
        hashed_password=get_test_password_hash("password_b"),
        is_active=True,
        is_admin=False
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def admin_user(test_db):
    """Create admin user for scoping tests."""
    user = User(
        username="admin",
        hashed_password=get_test_password_hash("adminpass"),
        is_active=True,
        is_admin=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def targets_for_users(test_db, user_a, user_b):
    """Create targets owned by different users."""
    target_a = Target(
        name="User A Target",
        user_id=user_a.id
    )
    target_b = Target(
        name="User B Target",
        user_id=user_b.id
    )
    test_db.add_all([target_a, target_b])
    test_db.commit()
    test_db.refresh(target_a)
    test_db.refresh(target_b)
    return {"user_a": target_a, "user_b": target_b}


@pytest.fixture
def judges_for_users(test_db, user_a, user_b):
    """Create judges owned by different users plus a baseline judge."""
    judge_a = Judge(
        name="User A Judge",
        model_name="gemini/gemini-2.5-flash-lite",
        prompt_template="Test template",
        params={},
        judge_type=JudgeTypeEnum.claim_based,
        is_baseline=False,
        is_editable=True,
        user_id=user_a.id
    )
    judge_b = Judge(
        name="User B Judge",
        model_name="gemini/gemini-2.5-flash-lite",
        prompt_template="Test template",
        params={},
        judge_type=JudgeTypeEnum.claim_based,
        is_baseline=False,
        is_editable=True,
        user_id=user_b.id
    )
    baseline_judge = Judge(
        name="Baseline Judge",
        model_name="gemini/gemini-2.5-flash-lite",
        prompt_template="Baseline template",
        params={},
        judge_type=JudgeTypeEnum.claim_based,
        is_baseline=True,
        is_editable=False,
        user_id=None  # Baseline judges have no user_id
    )
    test_db.add_all([judge_a, judge_b, baseline_judge])
    test_db.commit()
    test_db.refresh(judge_a)
    test_db.refresh(judge_b)
    test_db.refresh(baseline_judge)
    return {"user_a": judge_a, "user_b": judge_b, "baseline": baseline_judge}


@pytest.mark.integration
class TestTargetScoping:
    """Tests for target data scoping."""

    def test_user_sees_only_own_targets(
        self, scoping_test_app, user_a, user_b, targets_for_users
    ):
        """Test that non-admin user only sees their own targets."""
        client = TestClient(scoping_test_app)
        token_a = create_access_token(user_a.id)

        response = client.get(
            "/api/v1/targets",
            headers={"Authorization": f"Bearer {token_a}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "User A Target"

    def test_user_cannot_see_other_users_targets(
        self, scoping_test_app, user_a, user_b, targets_for_users
    ):
        """Test that User A cannot see User B's targets."""
        client = TestClient(scoping_test_app)
        token_a = create_access_token(user_a.id)

        response = client.get(
            "/api/v1/targets",
            headers={"Authorization": f"Bearer {token_a}"}
        )

        assert response.status_code == 200
        data = response.json()
        target_names = [t["name"] for t in data]
        assert "User B Target" not in target_names

    def test_admin_sees_all_targets(
        self, scoping_test_app, admin_user, user_a, user_b, targets_for_users
    ):
        """Test that admin user sees all targets."""
        client = TestClient(scoping_test_app)
        admin_token = create_access_token(admin_user.id)

        response = client.get(
            "/api/v1/targets",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        target_names = [t["name"] for t in data]
        assert "User A Target" in target_names
        assert "User B Target" in target_names


@pytest.mark.integration
class TestJudgeScoping:
    """Tests for judge data scoping."""

    def test_user_sees_own_judges_plus_baseline(
        self, scoping_test_app, user_a, user_b, judges_for_users
    ):
        """Test that non-admin user sees their own judges plus baseline judges."""
        client = TestClient(scoping_test_app)
        token_a = create_access_token(user_a.id)

        response = client.get(
            "/api/v1/judges",
            headers={"Authorization": f"Bearer {token_a}"}
        )

        assert response.status_code == 200
        data = response.json()
        judge_names = [j["name"] for j in data]
        # Should see own judge and baseline
        assert "User A Judge" in judge_names
        assert "Baseline Judge" in judge_names
        # Should NOT see User B's judge
        assert "User B Judge" not in judge_names

    def test_user_cannot_see_other_users_judges(
        self, scoping_test_app, user_a, user_b, judges_for_users
    ):
        """Test that User A cannot see User B's custom judges."""
        client = TestClient(scoping_test_app)
        token_a = create_access_token(user_a.id)

        response = client.get(
            "/api/v1/judges",
            headers={"Authorization": f"Bearer {token_a}"}
        )

        assert response.status_code == 200
        data = response.json()
        judge_names = [j["name"] for j in data]
        assert "User B Judge" not in judge_names

    def test_admin_sees_all_judges(
        self, scoping_test_app, admin_user, user_a, user_b, judges_for_users
    ):
        """Test that admin user sees all judges."""
        client = TestClient(scoping_test_app)
        admin_token = create_access_token(admin_user.id)

        response = client.get(
            "/api/v1/judges",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        judge_names = [j["name"] for j in data]
        assert "User A Judge" in judge_names
        assert "User B Judge" in judge_names
        assert "Baseline Judge" in judge_names
