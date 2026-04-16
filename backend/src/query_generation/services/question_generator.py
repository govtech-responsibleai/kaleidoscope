"""
Question generation service.

Generates questions for personas using LLM and prompt templates.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from sqlalchemy.orm import Session
from litellm import embedding

from src.common.llm import LLMClient, CostTracker
from src.common.prompts import render_template
from src.common.config import get_settings
from src.common.models import (
    QuestionBase,
    QuestionListOutput,
    QuestionScope,
    QuestionType,
)
from src.common.database.repositories import (
    TargetRepository,
    PersonaRepository,
    QuestionRepository,
    JobRepository,
    KBDocumentRepository,
    WebDocumentRepository,
)
from src.common.database.models import Persona, JobStatusEnum, QuestionSourceEnum

logger = logging.getLogger(__name__)


class QuestionGenerator:
    """Service for generating questions using LLM."""

    def __init__(
        self,
        db: Session,
        job_id: int,
        persona_ids: Optional[List[int]] = None,
        sample_questions: Optional[List[str]] = None,
        input_style: Optional[str] = None
    ):
        """
        Initialize question generator.

        Args:
            db: Database session
            job_id: Job ID for this generation run
            persona_ids: Optional list of persona IDs to generate for (overrides job config)
            sample_questions: Optional list of example questions
            input_style: Input style (brief, regular, detailed). Defaults to regular.
        """
        self.db = db
        self.job_id = job_id
        self.persona_ids = persona_ids  # Store for later use
        self.sample_questions = sample_questions or []
        self.input_style = input_style or "regular"
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
        Generate questions for the job.

        Uses persona_ids if provided during initialization.
        Else if job.persona_id is set, generates for that persona only.
        Otherwise, generates for all approved personas.

        Returns:
            List of generated question dictionaries

        Raises:
            Exception: If generation fails
        """
        try:
            logger.info(f"Starting question generation for job {self.job_id}")

            # Get personas to generate questions for
            if self.persona_ids:
                # Use provided persona IDs (batch query instead of N individual fetches)
                personas = (
                    self.db.query(Persona)
                    .filter(Persona.id.in_(self.persona_ids))
                    .all()
                )
                logger.info(f"Generating questions for {len(personas)} specified personas")
            elif self.job.persona_id:
                # Use single persona from job
                persona = PersonaRepository.get_by_id(self.db, self.job.persona_id)
                if not persona:
                    raise ValueError(f"Persona {self.job.persona_id} not found")
                personas = [persona]
                logger.info(f"Generating questions for single persona {self.job.persona_id}")
            else:
                # Use all approved personas for target
                personas = PersonaRepository.get_approved_by_target(
                    self.db,
                    self.target.id
                )
                logger.info(f"Generating questions for {len(personas)} approved personas")

            if not personas:
                raise ValueError("No personas found for question generation")

            all_questions_data = []
            batch_questions_text = []  # Accumulate texts to avoid overlap across buckets

            # Get web search context from stored WebDocuments
            web_text = WebDocumentRepository.get_compiled_context(
                self.db, self.target.id
            )

            # Get compiled KB text once (more efficient than retrieving per combination)
            kb_text = KBDocumentRepository.get_compiled_text(self.db, self.target.id)
            has_kb_content = kb_text is not None and kb_text.strip() != ""

            # Get question type/scope ratios from config
            settings = get_settings()
            if has_kb_content:
                ratios = settings.question_ratios_with_kb
            else:
                ratios = settings.question_ratios_no_kb
                logger.info("No KB content available, using no-KB ratios")

            # Pre-fetch data used across persona loop to avoid N+1 queries
            approved_questions = QuestionRepository.get_approved_by_target(
                self.db,
                self.target.id
            )
            allocations = self._allocate_question_counts(
                personas=personas,
                ratios=ratios,
                num_questions=self.job.count_requested
            )

            # Generate questions for each allocated persona/type/scope bucket
            for persona, question_type, question_scope, num_questions in allocations:
                logger.info(
                    f"Generating {num_questions} {question_type.value}/{question_scope.value} questions "
                    f"for persona {persona.id}: {persona.title}"
                )

                prompt = self._render_prompt(
                    persona,
                    approved_questions,
                    kb_text,
                    web_text,
                    question_type=question_type,
                    question_scope=question_scope,
                    num_questions=num_questions,
                    batch_questions=batch_questions_text,
                )

                question_list, metadata = self.llm_client.generate_structured(
                    prompt=prompt,
                    response_model=QuestionListOutput,
                    temperature=0.8,
                    max_tokens=4000
                )

                self.cost_tracker.add_call(metadata)

                actual_count = len(question_list.questions)
                if actual_count < num_questions:
                    logger.warning(
                        "LLM under-generated questions for persona %s %s/%s: "
                        "expected %s, got %s",
                        persona.id,
                        question_type.value,
                        question_scope.value,
                        num_questions,
                        actual_count,
                    )
                    questions_to_save = question_list.questions
                else:
                    questions_to_save = question_list.questions[:num_questions]

                logger.info(
                    f"Generated {len(questions_to_save)} {question_type.value}/{question_scope.value} "
                    f"questions for persona {persona.id}"
                )

                self._save_questions(questions_to_save, persona.id)
                all_questions_data.extend([q.model_dump() for q in questions_to_save])
                batch_questions_text.extend([q.text for q in questions_to_save])

            # Update job status
            self._update_job_status(JobStatusEnum.completed)

            self.cost_tracker.log_summary(prefix=f"Job {self.job_id}")

            return all_questions_data

        except Exception as e:
            logger.error(f"Question generation failed: {e}", exc_info=True)
            self._update_job_status(JobStatusEnum.failed)
            raise

    def _render_prompt(
        self,
        persona: Any,
        approved_questions: List[Any],
        kb_text: Optional[str],
        web_text: str,
        question_type: QuestionType,
        question_scope: QuestionScope,
        num_questions: int,
        batch_questions: Optional[List[str]] = None,
    ) -> str:
        """
        Render the question generation prompt template.

        Args:
            persona: Persona to generate questions for
            approved_questions: List of approved questions to avoid duplicates
            kb_text: Compiled KB text from documents (retrieved once in generate())
            web_text: Formatted web search results for grounding
            question_type: Type of questions
            question_scope: Scope of questions
            num_questions: Number of questions to request for this persona/type/scope bucket
            batch_questions: Questions already generated in this batch (to avoid overlap)

        Returns:
            Rendered prompt string
        """
        # Prepare approved questions for template
        approved_questions_text = [q.text for q in approved_questions]

        # Render template based on input style
        template_name = f"question_generation_{self.input_style}.md"
        prompt = render_template(
            template_name,
            target_name=self.target.name,
            purpose=self.target.purpose or "Not specified",
            target_users=self.target.target_users or "General users",
            agency=self.target.agency or "Not specified",
            persona={
                "title": persona.title,
                "info": persona.info,
                "style": persona.style,
                "use_case": persona.use_case
            },
            question_type=question_type.value,
            question_scope=question_scope.value,
            kb_text=kb_text,
            web_text=web_text,
            sample_questions=self.sample_questions,
            approved_questions=approved_questions_text if approved_questions_text else None,
            batch_questions=batch_questions if batch_questions else None,
            num_questions=num_questions,
        )

        return prompt

    def _allocate_question_counts(
        self,
        personas: List[Any],
        ratios: dict,
        num_questions: int
    ) -> List[Tuple[Any, QuestionType, QuestionScope, int]]:
        """
        Allocate total questions across persona/type/scope buckets using weighted ratios.

        Args:
            personas: List of personas to distribute across
            ratios: Dict mapping (type_str, scope_str) -> weight, from config
            num_questions: Total number of questions to generate

        Returns:
            List of (persona, question_type, question_scope, count) tuples
        """
        if num_questions < len(personas):
            raise ValueError(
                f"Question generation requires at least one question per persona: "
                f"requested {num_questions} for {len(personas)} personas"
            )

        # Convert string keys to enum pairs and compute per-combo counts
        type_map = {v.value: v for v in QuestionType}
        scope_map = {v.value: v for v in QuestionScope}

        combo_counts: list[tuple[QuestionType, QuestionScope, int]] = []
        total_weight = sum(ratios.values())
        allocated = 0

        for (type_str, scope_str), weight in ratios.items():
            count = round(num_questions * weight / total_weight)
            combo_counts.append((type_map[type_str], scope_map[scope_str], count))
            allocated += count

        # Adjust rounding errors on the largest bucket
        diff = num_questions - allocated
        if diff != 0 and combo_counts:
            max_idx = max(range(len(combo_counts)), key=lambda i: combo_counts[i][2])
            q_type, q_scope, count = combo_counts[max_idx]
            combo_counts[max_idx] = (q_type, q_scope, count + diff)

        # Distribute each combo's count evenly across personas
        results: list[tuple[Any, QuestionType, QuestionScope, int]] = []
        for q_type, q_scope, total_for_combo in combo_counts:
            if total_for_combo <= 0:
                continue
            base, remainder = divmod(total_for_combo, len(personas))
            for i, persona in enumerate(personas):
                count = base + (1 if i < remainder else 0)
                if count > 0:
                    results.append((persona, q_type, q_scope, count))

        return results

    def _save_questions(self, questions: List[QuestionBase], persona_id: int) -> List[Any]:
        """
        Save generated questions to database.

        Args:
            questions: List of QuestionBase Pydantic models
            persona_id: Persona ID

        Returns:
            List of saved Question objects
        """
        questions_to_create = []

        for question in questions:
            questions_to_create.append({
                "source": QuestionSourceEnum.job_generated,
                "job_id": self.job_id,
                "persona_id": persona_id,
                "target_id": self.target.id,
                "text": question.text,
                "type": question.type.value if hasattr(question.type, 'value') else question.type,
                "scope": question.scope.value if hasattr(question.scope, 'value') else question.scope,
                "input_style": self.input_style,
                "status": "pending"
            })

        # Save all questions
        questions_objs = QuestionRepository.create_many(self.db, questions_to_create)
        return questions_objs

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


def generate_questions_for_job(
    db: Session,
    job_id: int,
    persona_ids: Optional[List[int]] = None,
    sample_questions: Optional[List[str]] = None,
    input_style: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Generate questions for a job (convenience function).

    Args:
        db: Database session
        job_id: Job ID
        persona_ids: Optional list of persona IDs to generate for (overrides job config)
        sample_questions: Optional list of example questions
        input_style: Input style (brief, regular, detailed). Defaults to regular.

    Returns:
        List of generated question dictionaries
    """
    generator = QuestionGenerator(
        db,
        job_id,
        persona_ids=persona_ids,
        sample_questions=sample_questions,
        input_style=input_style
    )
    return generator.generate()


# Question Similarity Functions

def get_question_embedding(text: str, model: str = "gemini/gemini-embedding-001") -> List[float]:
    """
    Get embedding vector for a question text using Gemini's embedding model.

    Args:
        text: Question text to embed
        model: Embedding model to use (default: Gemini text-embedding-004)

    Returns:
        Embedding vector as a list of floats
    """
    try:
        response = embedding(
            model=model,
            input=[text]
        )
        return response.data[0]["embedding"]
    except Exception as e:
        logger.error(f"Failed to get embedding: {e}")
        raise


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity score (0-1)
    """
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)

    dot_product = np.dot(vec1_np, vec2_np)
    norm1 = np.linalg.norm(vec1_np)
    norm2 = np.linalg.norm(vec2_np)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))


def find_similar_questions_batch(
    query_texts: List[Tuple[int, str]],
    candidate_texts: List[Tuple[int, str]],
    threshold: float = 0.7,
    model: str = "gemini/gemini-embedding-001"
) -> Dict[int, List[Tuple[int, float]]]:
    """
    Find similar questions for multiple queries using matrix multiplication.

    Uses a single batch embedding call and matrix operations for maximum efficiency.

    For M queries and N candidates:
    - Old approach: M separate API calls + M * N similarity calculations
    - New approach: 1 batch API call + M×N matrix multiplication

    Args:
        query_texts: List of (question_id, text) tuples for queries
        candidate_texts: List of (question_id, text) tuples to compare against
        threshold: Minimum similarity threshold (0-1)
        model: Embedding model to use (default: Gemini text-embedding-004)

    Returns:
        Dictionary mapping query_question_id to list of (candidate_id, similarity_score) tuples,
        each sorted by score descending
    """
    if not query_texts or not candidate_texts:
        return {qid: [] for qid, _ in query_texts}

    try:
        # Extract IDs and texts
        query_ids = [qid for qid, _ in query_texts]
        query_text_list = [text for _, text in query_texts]
        candidate_ids = [qid for qid, _ in candidate_texts]
        candidate_text_list = [text for _, text in candidate_texts]

        # Batch: Get all embeddings at once (all queries + all candidates)
        all_texts = query_text_list + candidate_text_list
        response = embedding(
            model=model,
            input=all_texts
        )

        # Extract embeddings and convert to numpy arrays
        all_embeddings = [item["embedding"] for item in response.data]
        num_queries = len(query_text_list)

        query_embeddings = np.array(all_embeddings[:num_queries])  # Shape: (M, D)
        candidate_embeddings = np.array(all_embeddings[num_queries:])  # Shape: (N, D)

        # Matrix multiplication for all similarities at once
        # similarity_matrix[i, j] = similarity between query i and candidate j
        # Formula: (Q @ C.T) / (||Q|| * ||C||)

        # Calculate norms
        query_norms = np.linalg.norm(query_embeddings, axis=1, keepdims=True)  # Shape: (M, 1)
        candidate_norms = np.linalg.norm(candidate_embeddings, axis=1, keepdims=True)  # Shape: (N, 1)

        # Handle zero vectors
        query_norms = np.maximum(query_norms, 1e-10)
        candidate_norms = np.maximum(candidate_norms, 1e-10)

        # Normalize embeddings
        normalized_queries = query_embeddings / query_norms  # Shape: (M, D)
        normalized_candidates = candidate_embeddings / candidate_norms  # Shape: (N, D)

        # Matrix multiplication: (M, D) @ (D, N) = (M, N)
        similarity_matrix = normalized_queries @ normalized_candidates.T  # Shape: (M, N)

        # Build results for each query
        results = {}
        for i, query_id in enumerate(query_ids):
            # Get similarities for this query
            similarities = similarity_matrix[i]  # Shape: (N,)

            # Filter by threshold
            mask = similarities >= threshold
            filtered_ids = np.array(candidate_ids)[mask]
            filtered_scores = similarities[mask]

            # Sort by score descending
            sorted_indices = np.argsort(-filtered_scores)

            # Build result list
            results[query_id] = [
                (int(filtered_ids[idx]), float(filtered_scores[idx]))
                for idx in sorted_indices
            ]

        return results

    except Exception as e:
        logger.error(f"Failed to find similar questions: {e}")
        raise


def find_similar_questions(
    query_text: str,
    candidate_texts: List[Tuple[int, str]],
    threshold: float = 0.7,
    model: str = "gemini/gemini-embedding-001"
) -> List[Tuple[int, float]]:
    """
    Find similar questions from a list of candidates using cosine similarity.

    Uses batch embedding generation and vectorized numpy operations for efficiency.
    This is a convenience wrapper around find_similar_questions_batch for single queries.

    Args:
        query_text: The query question text
        candidate_texts: List of (question_id, text) tuples to compare against
        threshold: Minimum similarity threshold (0-1)
        model: Embedding model to use (default: Gemini text-embedding-004)

    Returns:
        List of (question_id, similarity_score) tuples, sorted by score descending
    """
    # Use a dummy ID for the single query
    query_texts = [(0, query_text)]
    results = find_similar_questions_batch(query_texts, candidate_texts, threshold, model)
    return results[0]
