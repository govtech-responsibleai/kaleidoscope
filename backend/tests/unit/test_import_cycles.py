"""Guard against import cycles that only surface outside pytest's import order."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "module",
    [
        "src.common.llm.provider_service",
        "src.rubric.services.system_rubrics",
        "experiments.rubricbench_calibration.run",
    ],
)
def test_module_imports_standalone(module: str) -> None:
    """Each module must import in a fresh interpreter with nothing else loaded first."""
    env = {**os.environ, "JWT_SECRET_KEY": "test", "ADMIN_API_KEY": "test"}
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
