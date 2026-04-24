"""
Registry of pre-made rubric templates that users can add to their targets.

Add new templates to PREMADE_RUBRIC_TEMPLATES to make them available.
Each entry must include:
- name
- criteria
- options
- best_option
- judge_prompt_path
- recommended_model_provider
- recommended_model_name
"""

from typing import Optional


PREMADE_RUBRIC_TEMPLATES: dict[str, dict] = {
    "empathy": {
        "name": "Empathy",
        "criteria": "Does the response demonstrate empathy and emotional awareness appropriate to the user's situation?",
        "options": [
            {"option": "Empathetic", "description": "The response acknowledges the user's situation and demonstrates appropriate emotional awareness."},
            {"option": "Not Empathetic", "description": "The response is impersonal, dismissive, or fails to acknowledge the user's emotional context."},
        ],
        "best_option": "Empathetic",
        "judge_prompt_path": "empathy_rubric_judge.md",
        "recommended_model_provider": "gemini",
        "recommended_model_name": "gemini/gemini-3-flash-preview",
    },
    "verbosity": {
        "name": "Verbosity",
        "criteria": "Is the response appropriately concise, or does it include unnecessary repetition, filler, or excessive detail?",
        "options": [
            {"option": "Concise", "description": "The response is appropriately sized for the question, without unnecessary repetition or filler."},
            {"option": "Verbose", "description": "The response includes unnecessary repetition, filler, or excessive detail beyond what was asked."},
        ],
        "best_option": "Concise",
        "judge_prompt_path": "verbosity_rubric_judge.md",
        "recommended_model_provider": "gemini",
        "recommended_model_name": "gemini/gemini-3.1-flash-lite-preview",
    },
}


def list_premade_templates() -> list[dict]:
    """Return summary info for all pre-made templates (excludes prompt bodies)."""
    return [
        {
            "name": tmpl["name"],
            "criteria": tmpl["criteria"],
            "options": tmpl["options"],
            "best_option": tmpl["best_option"],
            "recommended_model_provider": tmpl["recommended_model_provider"],
            "recommended_model_name": tmpl["recommended_model_name"],
            "group": "preset",
        }
        for key, tmpl in PREMADE_RUBRIC_TEMPLATES.items()
    ]


def get_premade_template(key: str) -> Optional[dict]:
    """Return the full template including judge prompt metadata, or None if not found."""
    return PREMADE_RUBRIC_TEMPLATES.get(key)
