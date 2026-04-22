"""Helpers for rubric judge prompt files."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from src.common.prompts.template_loader import get_loader

GENERATED_CUSTOM_PROMPTS_DIRNAME = "kaleidoscope_custom_rubric_prompts"


def templates_dir() -> Path:
    """Return the static prompt templates directory used by the loader."""
    return Path(get_loader().templates_dir)


def generated_custom_prompts_dir() -> Path:
    """Return the managed directory for generated custom rubric prompt files."""
    return Path(tempfile.gettempdir()) / GENERATED_CUSTOM_PROMPTS_DIRNAME / "custom_rubrics"


def load_prompt_template_text(template_name: str) -> str:
    """Load one static prompt template file by name."""
    template_path = templates_dir() / template_name
    try:
        return template_path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - critical startup failure if a static template is missing
        raise RuntimeError(f"Prompt template missing: {template_path}") from exc


def custom_rubric_prompt_template_name(rubric_id: int) -> str:
    """Return the managed template filename for one custom rubric."""
    return f"custom_rubrics/rubric_{rubric_id}.md"


def custom_rubric_prompt_path(rubric_id: int) -> Path:
    """Return the filesystem path for one generated custom rubric prompt."""
    return generated_custom_prompts_dir() / f"rubric_{rubric_id}.md"


def write_custom_rubric_prompt(rubric_id: int, prompt_text: str) -> str:
    """Persist one generated custom rubric prompt and return its template name."""
    template_path = custom_rubric_prompt_path(rubric_id)
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text(prompt_text, encoding="utf-8")
    return custom_rubric_prompt_template_name(rubric_id)


def load_custom_rubric_prompt(rubric_id: int) -> str | None:
    """Load one generated custom rubric prompt if it exists."""
    template_path = custom_rubric_prompt_path(rubric_id)
    if not template_path.exists():
        return None
    return template_path.read_text(encoding="utf-8")


def delete_custom_rubric_prompt(rubric_id: int) -> None:
    """Delete one generated custom rubric prompt file if it exists."""
    template_path = custom_rubric_prompt_path(rubric_id)
    if template_path.exists():
        template_path.unlink()


def resolve_rubric_prompt_text(rubric: Any) -> str | None:
    """Resolve the prompt text for a rubric, preferring managed custom prompt files."""
    if rubric is None:
        return None

    rubric_group = getattr(rubric, "group", None)
    rubric_id = getattr(rubric, "id", None)
    if rubric_group == "custom" and rubric_id is not None:
        custom_prompt = load_custom_rubric_prompt(int(rubric_id))
        if custom_prompt:
            return custom_prompt

    return getattr(rubric, "judge_prompt", None)
