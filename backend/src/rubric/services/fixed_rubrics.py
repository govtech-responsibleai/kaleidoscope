"""Registry of fixed rubric templates that are bootstrapped onto every target."""

from typing import Optional


FIXED_RUBRIC_TEMPLATES: dict[str, dict] = {
    "accuracy": {
        "name": "Accuracy",
        "criteria": "Are the claims in the response supported by the provided context, or do they contain hallucinations?",
        "options": [
            {"option": "Accurate", "description": "All claims are supported by the provided context."},
            {"option": "Inaccurate", "description": "One or more claims are unsupported or hallucinated."},
        ],
        "best_option": "Accurate",
        "judge_prompt_path": "accuracy_judge.md",
        "group": "fixed",
        "scoring_mode": "claim_based",
        "recommended_model_provider": "gemini",
        "recommended_model_name": "gemini/gemini-3.1-flash-lite-preview",
    },
}


def list_fixed_templates() -> list[dict]:
    """Return summary info for all fixed templates."""
    return [
        {
            "name": tmpl["name"],
            "criteria": tmpl["criteria"],
            "options": tmpl["options"],
            "best_option": tmpl["best_option"],
            "group": tmpl["group"],
            "scoring_mode": tmpl["scoring_mode"],
            "recommended_model_provider": tmpl["recommended_model_provider"],
            "recommended_model_name": tmpl["recommended_model_name"],
        }
        for tmpl in FIXED_RUBRIC_TEMPLATES.values()
    ]


def get_fixed_template(key: str) -> Optional[dict]:
    """Return a fixed template by registry key or name."""
    template = FIXED_RUBRIC_TEMPLATES.get(key)
    if template:
        return template
    lowered = key.strip().lower()
    for candidate in FIXED_RUBRIC_TEMPLATES.values():
        if candidate["name"].strip().lower() == lowered:
            return candidate
    return None
