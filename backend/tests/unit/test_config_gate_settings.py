import pytest
from pydantic import ValidationError

from src.common.config import Settings


@pytest.mark.unit
class TestGateSettings:
    def test_defaults(self):
        s = Settings(jwt_secret_key="x", admin_api_key="y", _env_file=None)
        assert s.reliability_threshold == 0.5
        assert s.min_calibration_samples == 20
        assert s.recommended_calibration_samples == 30

    def test_threshold_must_be_a_proportion(self):
        with pytest.raises(ValidationError):
            Settings(jwt_secret_key="x", admin_api_key="y", reliability_threshold=1.5, _env_file=None)

    def test_floor_must_be_positive_and_not_above_recommended(self):
        with pytest.raises(ValidationError):
            Settings(jwt_secret_key="x", admin_api_key="y", min_calibration_samples=0, _env_file=None)
        with pytest.raises(ValidationError):
            Settings(jwt_secret_key="x", admin_api_key="y", min_calibration_samples=40, recommended_calibration_samples=30, _env_file=None)
