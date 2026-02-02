"""
Persona sampling service.

Samples personas from the Nemotron dataset and maps them to the
Kaleidoscope persona schema using heuristic field mapping.
"""

import logging
import random
import re
from typing import List, Dict, Any

from datasets import load_dataset
from sqlalchemy.orm import Session

from src.common.database.repositories import TargetRepository, PersonaRepository
from src.common.database.models import PersonaSourceEnum

logger = logging.getLogger(__name__)

# Nemotron narrative fields eligible for random selection as persona `info`
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

# Singleton cache for the loaded dataset
_nemotron_dataset = None


def _load_nemotron_dataset():
    """
    Load the Nemotron personas dataset via HuggingFace (cached singleton).

    Returns:
        HuggingFace Dataset with all Nemotron persona rows.
    """
    global _nemotron_dataset
    if _nemotron_dataset is not None:
        return _nemotron_dataset

    logger.info("Loading Nemotron-Personas-Singapore dataset from HuggingFace")
    ds = load_dataset("nvidia/Nemotron-Personas-Singapore")
    _nemotron_dataset = ds["train"]
    logger.info(f"Loaded {len(_nemotron_dataset)} Nemotron personas")
    return _nemotron_dataset


def _deduplicate_title(title: str, taken_titles: set) -> str:
    """
    Append a numeric suffix if the title already exists.

    Args:
        title: Proposed title
        taken_titles: Set of titles already in use

    Returns:
        Unique title, e.g. "Suresh Kumar (2)" if "Suresh Kumar" is taken
    """
    if title not in taken_titles:
        return title
    counter = 2
    while f"{title} ({counter})" in taken_titles:
        counter += 1
    return f"{title} ({counter})"


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

        # Load target
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
        dataset = _load_nemotron_dataset()

        # Step 2: Random sample (no duplicates)
        if n > len(dataset):
            raise ValueError(
                f"Requested {n} personas but dataset only has {len(dataset)} rows"
            )
        indices = random.sample(range(len(dataset)), n)
        sampled = dataset.select(indices)

        # Step 3: Map each row to persona schema, deduplicating titles with suffix
        existing = PersonaRepository.get_by_target(
            self.db, self.target_id, status=None, skip=0, limit=10000
        )
        taken_titles = {p.title for p in existing}

        personas_data = []
        for row in sampled:
            mapped = self._map_nemotron_row(row)
            mapped["title"] = _deduplicate_title(mapped["title"], taken_titles)
            taken_titles.add(mapped["title"])
            personas_data.append(mapped)

        # Step 4: Save to DB
        personas = PersonaRepository.create_many(self.db, personas_data)
        logger.info(f"Saved {len(personas)} Nemotron personas for target {self.target_id}")

        return personas

    def _map_nemotron_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map a single Nemotron dataset row to Kaleidoscope persona schema.

        Args:
            row: Dict of Nemotron fields for one persona

        Returns:
            Dict matching the Persona model fields
        """
        # Title: extract name from persona text
        title = self._extract_name(row.get("persona", ""))

        # Info: random pick from narrative fields
        available_fields = [
            f for f in NEMOTRON_INFO_FIELDS
            if row.get(f) and str(row[f]).strip()
        ]
        info = row[random.choice(available_fields)] if available_fields else row.get("persona", "")

        # Style: demographic template
        sex = row.get("sex", "")
        pronoun = "She" if sex == "Female" else "He"
        age = row.get("age", "")
        marital_status = row.get("marital_status", "")
        occupation = row.get("occupation", "")
        industry = row.get("industry", "")
        style = (
            f"{pronoun} asks questions that a {age} year old, "
            f"{marital_status} {sex} who works as an {occupation} "
            f"in the {industry} industry would ask."
        )

        # Use case: generic
        pronoun_lower = "her" if sex == "Female" else "his"
        use_case = f"Wants to find answers to {pronoun_lower} questions"

        return {
            "source": PersonaSourceEnum.nemotron,
            "job_id": None,
            "target_id": self.target_id,
            "title": title,
            "info": info,
            "style": style,
            "use_case": use_case,
            "status": "pending",
        }

    @staticmethod
    def _extract_name(persona_text: str) -> str:
        """
        Extract the person's name from Nemotron persona text.

        Handles patterns like:
        - "Yi Peng Yong, known as Danelle, blends..."
        - "Yao Dar Teo (Daniel) splits his training..."
        - "Suresh Kumar enjoys..."

        Args:
            persona_text: Raw persona description from Nemotron

        Returns:
            Extracted name string
        """
        if not persona_text:
            return "Unknown"

        # Match consecutive capitalized words at the start
        name_match = re.match(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', persona_text)
        if not name_match:
            # Fallback: take text before first comma or parenthesis
            fallback = re.match(r'^([^,(]+)', persona_text)
            return fallback.group(1).strip() if fallback else "Unknown"

        return name_match.group(1).strip()


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
