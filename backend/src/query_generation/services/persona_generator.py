"""
Persona generation service.

Generates personas for a target using LLM and prompt templates.
"""

import logging
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from src.common.llm import LLMClient, CostTracker
from src.common.prompts import render_template
from src.common.models import PersonaListOutput, PersonaBase
from src.common.database.repositories import (
    TargetRepository,
    PersonaRepository,
    JobRepository
)
from src.common.database.models import JobStatusEnum

logger = logging.getLogger(__name__)


def _deduplicate_title(title: str, taken_titles: set) -> str:
    """
    Append a numeric suffix if the title already exists.

    Args:
        title: Proposed title
        taken_titles: Set of titles already in use

    Returns:
        Unique title, e.g. "Young Couple (2)" if "Young Couple" is taken
    """
    if title not in taken_titles:
        return title
    counter = 2
    while f"{title} ({counter})" in taken_titles:
        counter += 1
    return f"{title} ({counter})"


class PersonaGenerator:
    """Service for generating personas using LLM."""

    def __init__(
        self,
        db: Session,
        job_id: int,
        sample_personas: Optional[List[str]] = None
    ):
        """
        Initialize persona generator.

        Args:
            db: Database session
            job_id: Job ID for this generation run
            sample_personas: Optional list of example persona descriptions
        """
        self.db = db
        self.job_id = job_id
        self.sample_personas = sample_personas or []
        self.cost_tracker = CostTracker(job_id=job_id)

        # Load job
        self.job = JobRepository.get_by_id(db, job_id)
        if not self.job:
            raise ValueError(f"Job {job_id} not found")

        # Load target
        self.target = TargetRepository.get_by_id(db, self.job.target_id)
        if not self.target:
            raise ValueError(f"Target {self.job.target_id} not found")

        # Initialize LLM client
        self.llm_client = LLMClient(model=self.job.model_used)

    def generate(self) -> List[Dict[str, Any]]:
        """
        Generate personas for the target.

        Returns:
            List of generated persona dictionaries

        Raises:
            Exception: If generation fails
        """
        try:
            logger.info(f"Starting persona generation for job {self.job_id}")

            # Step 1: Get ALL existing personas to avoid duplicate titles
            # (unique constraint applies to all personas, not just approved)
            all_existing_personas = PersonaRepository.get_by_target(
                self.db,
                self.target.id,
                status=None,  # Get all statuses
                skip=0,
                limit=1000  # High limit to get all personas
            )

            # Step 2: Render prompt template
            prompt = self._render_prompt(all_existing_personas)
            logger.info(f"Rendered prompt ({len(prompt)} chars)")

            # Step 3: Call LLM with structured output
            persona_list, metadata = self.llm_client.generate_structured(
                prompt=prompt,
                response_model=PersonaListOutput,
                temperature=0.8,  # Higher temperature for diversity
                max_tokens=4000
            )

            # Track costs
            self.cost_tracker.add_call(metadata)

            logger.info(f"Generated {len(persona_list.personas)} personas")

            # Step 4: Save personas to database
            personas = self._save_personas(persona_list.personas)
            logger.info(f"Saved {len(personas)} personas to database")

            # Step 5: Update job status
            self._update_job_status(JobStatusEnum.completed)

            self.cost_tracker.log_summary(prefix=f"Job {self.job_id}")

            # Return as dicts for API response
            return [persona.model_dump() for persona in persona_list.personas]

        except Exception as e:
            logger.error(f"Persona generation failed: {e}", exc_info=True)
            self._update_job_status(JobStatusEnum.failed)
            raise

    def _render_prompt(self, existing_personas: List[Any]) -> str:
        """
        Render the persona generation prompt template.

        Args:
            existing_personas: List of all existing personas to avoid duplicate titles

        Returns:
            Rendered prompt string
        """
        # Prepare existing personas for template
        existing_personas_data = [
            {
                "title": p.title,
                "info": p.info,
                "style": p.style,
                "use_case": p.use_case
            }
            for p in existing_personas
        ]

        # Render template
        prompt = render_template(
            "persona_generation.md",
            chatbot_name=self.target.name,
            purpose=self.target.purpose or "Not specified",
            target_users=self.target.target_users or "General users",
            agency=self.target.agency or "Not specified",
            sample_personas=self.sample_personas,
            target_persona_count=self.job.count_requested,
            approved_personas=existing_personas_data if existing_personas_data else None
        )

        return prompt

    def _save_personas(self, personas_data: List[PersonaBase]) -> List[Any]:
        """
        Save generated personas to database, deduplicating titles with suffix.

        Args:
            personas_data: List of PersonaBase Pydantic models

        Returns:
            List of saved Persona objects
        """
        existing = PersonaRepository.get_by_target(
            self.db, self.target.id, status=None, skip=0, limit=10000
        )
        taken_titles = {p.title for p in existing}

        personas_to_create = []

        for persona in personas_data:
            title = _deduplicate_title(persona.title, taken_titles)
            taken_titles.add(title)
            personas_to_create.append({
                "job_id": self.job_id,
                "target_id": self.target.id,
                "title": title,
                "info": persona.info,
                "style": persona.style,
                "use_case": persona.use_case,
                "status": "pending"
            })

        # Save all personas
        personas = PersonaRepository.create_many(self.db, personas_to_create)
        return personas

    def _update_job_status(
        self,
        status: JobStatusEnum,
        error_message: Optional[str] = None
    ):
        """
        Update job status and costs in database.

        Args:
            status: New job status
            error_message: Optional error message if failed
        """
        summary = self.cost_tracker.get_summary()

        JobRepository.update_status(
            self.db,
            self.job_id,
            status=status,
            prompt_tokens=summary["prompt_tokens"],
            completion_tokens=summary["completion_tokens"],
            total_cost=summary["total_cost"]
        )

        logger.info(f"Updated job {self.job_id} status to {status.value}")


def generate_personas_for_job(
    db: Session,
    job_id: int,
    sample_personas: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Generate personas for a job (convenience function).

    Args:
        db: Database session
        job_id: Job ID
        sample_personas: Optional list of example persona descriptions

    Returns:
        List of generated persona dictionaries
    """
    generator = PersonaGenerator(
        db,
        job_id,
        sample_personas=sample_personas
    )
    return generator.generate()
