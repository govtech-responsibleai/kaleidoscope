"""
Persona sampling service.

Samples personas from the Nemotron dataset and maps them to the
Kaleidoscope persona schema using per-dataset style templates.
"""

import logging
import random
import re
from typing import List, Dict, Any, Callable

from datasets import load_dataset
from sqlalchemy.orm import Session

from src.common.config import get_settings
from src.common.database.repositories import TargetRepository, PersonaRepository
from src.common.database.models import PersonaSourceEnum

logger = logging.getLogger(__name__)

# Narrative fields eligible for random selection as persona `info`.
# Already resilient: only fields that exist and are non-empty are considered.
NEMOTRON_INFO_FIELDS = [
    "professional_persona",
    "sports_persona",
    "arts_persona",
    "travel_persona",
    "culinary_persona",
    "persona",
    "cultural_background",
    "skills_and_expertise",
    "hobbies_and_interests",
    "career_goals_and_ambitions",
]


# ---------------------------------------------------------------------------
# Dataset name validation
# ---------------------------------------------------------------------------

def _validate_dataset_name(dataset_name: str) -> None:
    # Soft check: we don't maintain a country allowlist, but we do reject
    # values that clearly aren't NVIDIA Nemotron datasets to avoid cryptic
    # HuggingFace errors deep in the stack.
    lower = dataset_name.lower()
    if "nvidia" not in lower or "nemotron" not in lower:
        raise ValueError(
            f"NEMOTRON_PERSONAS_DATASET={dataset_name!r} does not look like a "
            f"Nemotron dataset (expected 'nvidia' and 'nemotron' in the name). "
            f"Example: 'nvidia/Nemotron-Personas-Singapore'."
        )


# ---------------------------------------------------------------------------
# Style templates — one per dataset, keyed by full HF dataset name.
# Schemas differ across countries (e.g. Singapore has `industry`;
# USA has `city`/`state`/`education_level` instead).
# ---------------------------------------------------------------------------

StyleFn = Callable[[Dict[str, Any]], str]


def _singapore_style(row: Dict[str, Any]) -> str:
    # Singapore schema includes `industry` (Nemotron-Personas-Singapore).
    sex = row.get("sex", "")
    pronoun = "She" if sex == "Female" else "He"
    return (
        f"{pronoun} asks questions that a {row.get('age', '')} year old, "
        f"{row.get('marital_status', '')} {sex} who works as an "
        f"{row.get('occupation', '')} in the {row.get('industry', '')} "
        f"industry would ask."
    )


def _usa_style(row: Dict[str, Any]) -> str:
    # USA schema replaces `industry` with `city`/`state`/`education_level`.
    sex = row.get("sex", "")
    pronoun = "She" if sex == "Female" else "He"
    return (
        f"{pronoun} asks questions that a {row.get('age', '')} year old, "
        f"{row.get('marital_status', '')} {sex} from {row.get('city', '')}, "
        f"{row.get('state', '')}, working as a {row.get('occupation', '')}, "
        f"with {row.get('education_level', '')} education would ask."
    )


def _generic_style(_row: Dict[str, Any]) -> str:
    # Used when no template matches the configured dataset.
    return "Asks questions a typical user from this region might ask."


# Templates keyed by full HF dataset name so swapping the env var routes
# directly to the right template with no parsing.
STYLE_TEMPLATES: Dict[str, StyleFn] = {
    "nvidia/Nemotron-Personas-Singapore": _singapore_style,
    "nvidia/Nemotron-Personas-USA": _usa_style,
}

# Required columns per template — checked at first load to surface schema
# drift in NVIDIA's datasets (logged as a warning, not a hard failure).
TEMPLATE_REQUIRED_COLUMNS: Dict[str, List[str]] = {
    "nvidia/Nemotron-Personas-Singapore": ["sex", "age", "marital_status", "occupation", "industry"],
    "nvidia/Nemotron-Personas-USA": ["sex", "age", "marital_status", "occupation", "city", "state", "education_level"],
}


# Datasets where the `persona` field starts with a Latin-script name that the
# regex extractor can reliably parse. All other datasets fall back to alphabetic.
NAME_EXTRACTION_DATASETS = {
    "nvidia/Nemotron-Personas-Singapore",
    "nvidia/Nemotron-Personas-USA",
}


# ---------------------------------------------------------------------------
# Title helpers
# ---------------------------------------------------------------------------

def _extract_name(persona_text: str) -> str:
    """
    Extract the person's name from Nemotron persona text.

    Handles patterns like:
    - "Yi Peng Yong, known as Danelle, blends..."
    - "Yao Dar Teo (Daniel) splits his training..."
    - "John Smith enjoys..."

    Args:
        persona_text: Raw persona description from Nemotron

    Returns:
        Extracted name string, or "Unknown" if not found
    """
    if not persona_text:
        return "Unknown"

    # Match consecutive capitalized words at the start
    name_match = re.match(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', persona_text)
    if not name_match:
        fallback = re.match(r'^([^,(]+)', persona_text)
        return fallback.group(1).strip() if fallback else "Unknown"

    return name_match.group(1).strip()


def _alpha_label(i: int) -> str:
    # 0 -> "A", 25 -> "Z", 26 -> "AA", … (base-26, Excel-column style)
    # so titles stay short and predictably ordered.
    s = ""
    n = i
    while True:
        s = chr(ord("A") + (n % 26)) + s
        n = n // 26 - 1
        if n < 0:
            return s


def _deduplicate_title(title: str, taken_titles: set) -> str:
    """
    Append a numeric suffix if the title already exists.

    Args:
        title: Proposed title
        taken_titles: Set of titles already in use

    Returns:
        Unique title, e.g. "Persona A (2)" if "Persona A" is taken
    """
    if title not in taken_titles:
        return title
    counter = 2
    while f"{title} ({counter})" in taken_titles:
        counter += 1
    return f"{title} ({counter})"


# ---------------------------------------------------------------------------
# Dataset loader (process-lifetime singleton)
# ---------------------------------------------------------------------------

_nemotron_dataset = None
_nemotron_dataset_name: str = ""


def _load_nemotron_dataset() -> tuple[Any, str]:
    # Singleton: dataset name is fixed for the process lifetime (deploy-time config).
    global _nemotron_dataset, _nemotron_dataset_name
    if _nemotron_dataset is not None and _nemotron_dataset_name:
        return _nemotron_dataset, _nemotron_dataset_name

    settings = get_settings()
    dataset_name = settings.nemotron_personas_dataset
    _validate_dataset_name(dataset_name)

    logger.info(f"Loading {dataset_name} from HuggingFace")
    try:
        ds = load_dataset(dataset_name)
    except Exception as e:
        # Wrap HF errors so the user sees the env var that drove the call.
        raise RuntimeError(
            f"Failed to load Nemotron dataset {dataset_name!r}: {e}. "
            f"Check NEMOTRON_PERSONAS_DATASET — it must be a valid HuggingFace "
            f"dataset path published by NVIDIA."
        ) from e

    train = ds["train"]
    columns = set(train.column_names)

    # Hard requirement: `persona` is the only column every code path depends on.
    if "persona" not in columns:
        raise RuntimeError(
            f"Dataset {dataset_name!r} is missing required column 'persona'."
        )

    # Soft requirement: warn if the chosen template's columns are missing,
    # or if no template is registered for this dataset.
    required = TEMPLATE_REQUIRED_COLUMNS.get(dataset_name)
    if required:
        missing = [c for c in required if c not in columns]
        if missing:
            logger.warning(
                f"Dataset {dataset_name!r} is missing columns {missing} "
                f"required by its style template. Style strings may have empty gaps."
            )
    else:
        logger.warning(
            f"No style template registered for {dataset_name!r}. "
            f"Using generic fallback. To add one, update STYLE_TEMPLATES in "
            f"backend/src/query_generation/services/persona_sampler.py."
        )

    _nemotron_dataset = train
    _nemotron_dataset_name = dataset_name
    logger.info(f"Loaded {len(_nemotron_dataset)} Nemotron personas")
    return _nemotron_dataset, _nemotron_dataset_name


# ---------------------------------------------------------------------------
# PersonaSampler
# ---------------------------------------------------------------------------

class PersonaSampler:
    """Service for sampling personas from the Nemotron dataset."""

    def __init__(self, db: Session, target_id: int):
        """
        Initialize persona sampler.

        Args:
            db: Database session
            target_id: Target ID to associate personas with
        """
        self.db = db
        self.target_id = target_id

        self.target = TargetRepository.get_by_id(db, target_id)
        if not self.target:
            raise ValueError(f"Target {target_id} not found")

    def sample(self, n: int) -> List[Any]:
        """
        Sample n personas from the Nemotron dataset and save to DB.

        Args:
            n: Number of personas to sample

        Returns:
            List of saved Persona ORM objects
        """
        logger.info(f"Sampling {n} Nemotron personas for target {self.target_id}")

        # Step 1: Load dataset
        dataset, dataset_name = _load_nemotron_dataset()

        # Step 2: Random sample (no duplicates)
        if n > len(dataset):
            raise ValueError(
                f"Requested {n} personas but dataset only has {len(dataset)} rows"
            )
        indices = random.sample(range(len(dataset)), n)
        sampled = dataset.select(indices)

        # Step 3: Map rows, assigning titles.
        # Latin-script datasets (Singapore, USA) use regex name extraction;
        # other datasets fall back to alphabetic (Persona A, B, …).
        existing = PersonaRepository.get_by_target(
            self.db, self.target_id, status=None, skip=0, limit=10000
        )
        taken_titles = {str(p.title) for p in existing}

        use_name_extraction = dataset_name in NAME_EXTRACTION_DATASETS
        alpha_counter = 0
        personas_data = []
        for row in sampled:
            if use_name_extraction:
                name = _extract_name(row.get("persona", ""))
                base_title = name if name != "Unknown" else f"Persona {_alpha_label(alpha_counter)}"
                if base_title != name:
                    alpha_counter += 1
            else:
                base_title = f"Persona {_alpha_label(alpha_counter)}"
                alpha_counter += 1
            title = _deduplicate_title(base_title, taken_titles)
            taken_titles.add(title)
            mapped = self._map_nemotron_row(row, dataset_name)
            mapped["title"] = title
            personas_data.append(mapped)

        # Step 4: Save to DB
        personas = PersonaRepository.create_many(self.db, personas_data)
        logger.info(f"Saved {len(personas)} Nemotron personas for target {self.target_id}")

        return personas

    def _map_nemotron_row(self, row: Dict[str, Any], dataset_name: str) -> Dict[str, Any]:
        """
        Map a single Nemotron dataset row to Kaleidoscope persona schema.

        Args:
            row: Dict of Nemotron fields for one persona
            dataset_name: Full HF dataset name, used to select the style template

        Returns:
            Dict matching the Persona model fields (title is set by caller)
        """
        # Info: random pick from available narrative fields
        available_fields = [
            f for f in NEMOTRON_INFO_FIELDS
            if row.get(f) and str(row[f]).strip()
        ]
        info = row[random.choice(available_fields)] if available_fields else row.get("persona", "")

        # Style: use the registered template for this dataset, or generic fallback
        style_fn = STYLE_TEMPLATES.get(dataset_name, _generic_style)
        style = style_fn(row)

        sex = row.get("sex", "")
        pronoun_lower = "her" if sex == "Female" else "his"
        use_case = f"Wants to find answers to {pronoun_lower} questions"

        return {
            "source": PersonaSourceEnum.nemotron,
            "job_id": None,
            "target_id": self.target_id,
            "title": "",  # overwritten by caller
            "info": info,
            "style": style,
            "use_case": use_case,
            "status": "pending",
        }


def sample_personas_from_nemotron(
    db: Session,
    target_id: int,
    n: int
) -> List[Any]:
    """
    Sample personas from the Nemotron dataset (convenience function).

    Args:
        db: Database session
        target_id: Target ID
        n: Number of personas to sample

    Returns:
        List of saved Persona ORM objects
    """
    sampler = PersonaSampler(db, target_id)
    return sampler.sample(n)
