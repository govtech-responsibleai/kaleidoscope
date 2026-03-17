"""
Unit tests for QuestionGenerator service.
"""

import pytest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

from src.common.database.models import JobStatusEnum
from src.common.models import QuestionBase, QuestionListOutput, QuestionScope, QuestionType
from src.query_generation.services.question_generator import (
    QuestionGenerator,
    cosine_similarity,
    find_similar_questions,
    find_similar_questions_batch,
    get_question_embedding,
)

def _make_llm_result(n=2):
    """Create a fake QuestionListOutput + metadata tuple."""
    questions = [
        QuestionBase(text=f"Question {i}?", type=QuestionType.typical, scope=QuestionScope.in_kb)
        for i in range(n)
    ]
    result = QuestionListOutput(questions=questions)
    metadata = {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_cost": 0.001,
        "model": "gpt-4o-mini",
    }
    return result, metadata


def _make_generator(test_db, sample_job, sample_target, count_requested=None):
    with patch.object(QuestionGenerator, '__init__', lambda self, *a, **kw: None):
        gen = QuestionGenerator.__new__(QuestionGenerator)
        gen.db = test_db
        gen.job_id = sample_job.id
        gen.job = sample_job
        if count_requested is not None:
            gen.job.count_requested = count_requested
        gen.target = sample_target
        gen.persona_ids = None
        gen.sample_questions = []
        gen.input_style = "regular"
        gen.cost_tracker = MagicMock()
        gen.cost_tracker.get_summary.return_value = {
            "prompt_tokens": 0, "completion_tokens": 0, "total_cost": 0.0,
        }
        gen.llm_client = MagicMock()
        gen.llm_client.generate_structured.return_value = _make_llm_result(1)
        return gen


@pytest.mark.unit
class TestQuestionGenerator:
    """Unit tests for question generation logic."""

    def test_generate_no_kb_uses_only_out_kb_combos(
        self, test_db, sample_job, sample_target, sample_personas
    ):
        """Without KB content, only out_kb combinations should be used (2 combos)."""
        gen = _make_generator(test_db, sample_job, sample_target)
        gen.llm_client.generate_structured.side_effect = [
            _make_llm_result(2),
            _make_llm_result(1),
        ]

        # Patch KB to return empty
        with patch(
            "src.query_generation.services.question_generator.KBDocumentRepository"
        ) as mock_kb, patch(
            "src.query_generation.services.question_generator.PersonaRepository"
        ) as mock_persona, patch(
            "src.query_generation.services.question_generator.QuestionRepository"
        ) as mock_qr, patch(
            "src.query_generation.services.question_generator.JobRepository"
        ) as mock_jr:
            mock_kb.get_compiled_text.return_value = ""  # No KB content
            mock_persona.get_approved_by_target.return_value = [sample_personas[0]]
            mock_qr.get_approved_by_target.return_value = []
            mock_qr.create_many.return_value = []

            result = gen.generate()

        # Only 2 buckets are active without KB for one persona.
        assert gen.llm_client.generate_structured.call_count == 2
        assert len(result) == 3

    def test_generate_with_kb_uses_weighted_combos(
        self, test_db, sample_job, sample_target, sample_personas
    ):
        """With KB content, questions are distributed per weighted ratios (70/10/15/5)."""
        # Use 20 questions so all 4 combos get at least 1
        gen = _make_generator(test_db, sample_job, sample_target, count_requested=20)
        # Return enough questions per call to satisfy allocation
        gen.llm_client.generate_structured.return_value = _make_llm_result(20)

        with patch(
            "src.query_generation.services.question_generator.KBDocumentRepository"
        ) as mock_kb, patch(
            "src.query_generation.services.question_generator.PersonaRepository"
        ) as mock_persona, patch(
            "src.query_generation.services.question_generator.QuestionRepository"
        ) as mock_qr, patch(
            "src.query_generation.services.question_generator.JobRepository"
        ) as mock_jr:
            mock_kb.get_compiled_text.return_value = "Some KB content here"
            mock_persona.get_approved_by_target.return_value = [sample_personas[0]]
            mock_qr.get_approved_by_target.return_value = []
            mock_qr.create_many.return_value = []

            result = gen.generate()

        # All 4 combos should have at least 1 question with 20 total
        assert gen.llm_client.generate_structured.call_count == 4
        assert len(result) == 20

    def test_generate_truncates_over_generated_bucket(
        self, test_db, sample_job, sample_target, sample_personas
    ):
        """Over-generated buckets should be truncated to the allocated count."""
        gen = _make_generator(test_db, sample_job, sample_target, count_requested=1)
        gen._save_questions = MagicMock(return_value=[])
        gen.llm_client.generate_structured.return_value = _make_llm_result(3)

        with patch(
            "src.query_generation.services.question_generator.KBDocumentRepository"
        ) as mock_kb, patch(
            "src.query_generation.services.question_generator.PersonaRepository"
        ) as mock_persona, patch(
            "src.query_generation.services.question_generator.QuestionRepository"
        ) as mock_qr, patch(
            "src.query_generation.services.question_generator.JobRepository"
        ) as mock_jr:
            mock_kb.get_compiled_text.return_value = ""
            mock_persona.get_approved_by_target.return_value = [sample_personas[0]]
            mock_qr.get_approved_by_target.return_value = []

            result = gen.generate()

        saved_questions = gen._save_questions.call_args[0][0]
        assert len(saved_questions) == 1
        assert len(result) == 1

    def test_generate_under_generated_bucket_logs_warning(
        self, test_db, sample_job, sample_target, sample_personas
    ):
        """Under-generated buckets should be kept and logged as a warning."""
        # With no KB ratios (80/20) and 1 persona, requesting 4:
        # typical/out_kb gets 3, edge/out_kb gets 1.
        # LLM returns 1 per call, so typical bucket under-generates (expected 3, got 1).
        gen = _make_generator(test_db, sample_job, sample_target, count_requested=4)
        gen._save_questions = MagicMock(return_value=[])
        gen.llm_client.generate_structured.return_value = _make_llm_result(1)

        with patch(
            "src.query_generation.services.question_generator.KBDocumentRepository"
        ) as mock_kb, patch(
            "src.query_generation.services.question_generator.PersonaRepository"
        ) as mock_persona, patch(
            "src.query_generation.services.question_generator.QuestionRepository"
        ) as mock_qr, patch(
            "src.query_generation.services.question_generator.JobRepository"
        ) as mock_jr, patch(
            "src.query_generation.services.question_generator.logger"
        ) as mock_logger:
            mock_kb.get_compiled_text.return_value = ""
            mock_persona.get_approved_by_target.return_value = [sample_personas[0]]
            mock_qr.get_approved_by_target.return_value = []

            result = gen.generate()

        # 2 buckets, LLM returns 1 each = 2 total
        assert len(result) == 2
        # typical/out_kb bucket under-generated (expected 3, got 1) = 1 warning
        assert mock_logger.warning.call_count == 1

    def test_allocate_question_counts_respects_ratios(self, test_db, sample_job, sample_target):
        """Allocation should distribute questions according to weighted ratios."""
        gen = _make_generator(test_db, sample_job, sample_target)
        personas = [SimpleNamespace(id=1, title="A")]
        ratios = {
            ("typical", "in_kb"): 0.70,
            ("typical", "out_kb"): 0.10,
            ("edge", "in_kb"): 0.15,
            ("edge", "out_kb"): 0.05,
        }

        allocations = gen._allocate_question_counts(
            personas=personas,
            ratios=ratios,
            num_questions=20
        )

        counts = {(q_type.value, q_scope.value): count for _, q_type, q_scope, count in allocations}
        assert counts[("typical", "in_kb")] == 14
        assert counts[("edge", "in_kb")] == 3
        assert counts[("typical", "out_kb")] == 2
        assert counts[("edge", "out_kb")] == 1
        assert sum(count for _, _, _, count in allocations) == 20

    def test_allocate_question_counts_distributes_across_personas(self, test_db, sample_job, sample_target):
        """Allocation should distribute each combo's count evenly across personas."""
        gen = _make_generator(test_db, sample_job, sample_target)
        personas = [
            SimpleNamespace(id=1, title="A"),
            SimpleNamespace(id=2, title="B"),
        ]
        ratios = {("typical", "out_kb"): 0.80, ("edge", "out_kb"): 0.20}

        allocations = gen._allocate_question_counts(
            personas=personas,
            ratios=ratios,
            num_questions=10
        )

        assert sum(count for _, _, _, count in allocations) == 10

    def test_allocate_question_counts_raises_when_num_questions_less_than_personas(
        self, test_db, sample_job, sample_target
    ):
        """Allocation should enforce at least one question per persona."""
        gen = _make_generator(test_db, sample_job, sample_target)
        personas = [
            SimpleNamespace(id=1, title="A"),
            SimpleNamespace(id=2, title="B"),
            SimpleNamespace(id=3, title="C"),
        ]

        with pytest.raises(ValueError, match="at least one question per persona"):
            gen._allocate_question_counts(
                personas=personas,
                ratios={("typical", "out_kb"): 1.0},
                num_questions=2
            )

    def test_generate_multi_persona_uses_allocated_counts(
        self, test_db, sample_job, sample_target, sample_personas
    ):
        """generate() should batch by allocated bucket counts, not raw persona x combo count."""
        gen = _make_generator(test_db, sample_job, sample_target, count_requested=3)
        gen.job.persona_id = None
        gen.persona_ids = [sample_personas[0].id, sample_personas[1].id]
        rendered_counts = []

        def fake_render_prompt(*args, **kwargs):
            rendered_counts.append(kwargs["num_questions"])
            return "prompt"

        gen._render_prompt = MagicMock(side_effect=fake_render_prompt)

        with patch(
            "src.query_generation.services.question_generator.KBDocumentRepository"
        ) as mock_kb, patch(
            "src.query_generation.services.question_generator.PersonaRepository"
        ) as mock_persona, patch(
            "src.query_generation.services.question_generator.QuestionRepository"
        ) as mock_qr, patch(
            "src.query_generation.services.question_generator.JobRepository"
        ) as mock_jr:
            mock_kb.get_compiled_text.return_value = ""
            mock_persona.get_by_id.side_effect = lambda db, pid: (
                sample_personas[0] if pid == sample_personas[0].id else sample_personas[1]
            )
            mock_qr.get_approved_by_target.return_value = []
            mock_qr.create_many.return_value = []

            result = gen.generate()

        assert rendered_counts == [1, 1, 1]
        assert gen.llm_client.generate_structured.call_count == 3
        assert len(result) == 3

    def test_generate_failure_sets_job_failed(
        self, test_db, sample_job, sample_target, sample_personas
    ):
        """If LLM call fails, job should be set to failed status."""
        gen = _make_generator(test_db, sample_job, sample_target)
        gen.llm_client.generate_structured.side_effect = RuntimeError("LLM down")

        with patch(
            "src.query_generation.services.question_generator.KBDocumentRepository"
        ) as mock_kb, patch(
            "src.query_generation.services.question_generator.PersonaRepository"
        ) as mock_persona, patch(
            "src.query_generation.services.question_generator.QuestionRepository"
        ) as mock_qr, patch(
            "src.query_generation.services.question_generator.JobRepository"
        ) as mock_jr:
            mock_kb.get_compiled_text.return_value = ""
            mock_persona.get_approved_by_target.return_value = [sample_personas[0]]
            mock_qr.get_approved_by_target.return_value = []

            with pytest.raises(RuntimeError, match="LLM down"):
                gen.generate()

        # Verify job was marked failed
        mock_jr.update_status.assert_called()
        call_args = mock_jr.update_status.call_args
        assert call_args[1]["status"] == JobStatusEnum.failed or call_args[0][2] == JobStatusEnum.failed


@pytest.mark.unit
class TestQuestionSimilarity:
    """Unit tests for question similarity functions."""

    def test_cosine_similarity_identical_vectors(self):
        """Test cosine similarity with identical vectors returns 1.0."""
        vec1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        vec2 = [1.0, 2.0, 3.0, 4.0, 5.0]

        similarity = cosine_similarity(vec1, vec2)

        assert similarity == pytest.approx(1.0, abs=1e-6)

    def test_cosine_similarity_orthogonal_vectors(self):
        """Test cosine similarity with orthogonal vectors returns 0.0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        similarity = cosine_similarity(vec1, vec2)

        assert similarity == pytest.approx(0.0, abs=1e-6)

    def test_cosine_similarity_opposite_vectors(self):
        """Test cosine similarity with opposite vectors returns -1.0."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [-1.0, -2.0, -3.0]

        similarity = cosine_similarity(vec1, vec2)

        assert similarity == pytest.approx(-1.0, abs=1e-6)

    def test_cosine_similarity_zero_vector(self):
        """Test cosine similarity with zero vector returns 0.0."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [0.0, 0.0, 0.0]

        similarity = cosine_similarity(vec1, vec2)

        assert similarity == 0.0

    def test_cosine_similarity_similar_vectors(self):
        """Test cosine similarity with similar vectors returns high score."""
        vec1 = [1.0, 2.0, 3.0, 4.0]
        vec2 = [1.1, 2.1, 3.1, 4.1]

        similarity = cosine_similarity(vec1, vec2)

        # Should be very close to 1.0 for similar vectors
        assert similarity > 0.99

    @patch('src.query_generation.services.question_generator.embedding')
    def test_get_question_embedding_success(self, mock_embedding):
        """Test successful embedding generation."""
        # Mock the embedding API response
        mock_embedding.return_value.data = [
            {"embedding": [0.1, 0.2, 0.3, 0.4, 0.5]}
        ]

        embedding_result = get_question_embedding("What is AI?")

        assert embedding_result == [0.1, 0.2, 0.3, 0.4, 0.5]
        mock_embedding.assert_called_once_with(
            model="gemini/gemini-embedding-001",
            input=["What is AI?"]
        )

    @patch('src.query_generation.services.question_generator.embedding')
    def test_get_question_embedding_with_custom_model(self, mock_embedding):
        """Test embedding generation with custom model."""
        mock_embedding.return_value.data = [
            {"embedding": [0.1, 0.2, 0.3]}
        ]

        embedding_result = get_question_embedding("Test question", model="custom/model")

        assert embedding_result == [0.1, 0.2, 0.3]
        mock_embedding.assert_called_once_with(
            model="custom/model",
            input=["Test question"]
        )

    @patch('src.query_generation.services.question_generator.embedding')
    def test_find_similar_questions_identical_text(self, mock_embedding):
        """Test finding similar questions with identical text returns score of 1.0."""
        # Mock batch embedding response
        identical_vector = [0.5, 0.5, 0.5, 0.5, 0.5]
        different_vector = [0.1, 0.9, 0.0, 0.0, 0.0]

        mock_embedding.return_value.data = [
            {"embedding": identical_vector},  # Query
            {"embedding": identical_vector},  # Candidate 1 - identical
            {"embedding": different_vector}   # Candidate 2 - different
        ]

        query_text = "What are the risks of AI?"
        candidate_texts = [
            (1, "What are the risks of AI?"),  # Identical text
            (2, "How does machine learning work?")
        ]

        results = find_similar_questions(query_text, candidate_texts, threshold=0.9)

        # Should find the identical question with similarity 1.0
        assert len(results) >= 1
        assert results[0][0] == 1  # Question ID 1
        assert results[0][1] == pytest.approx(1.0, abs=1e-6)

    @patch('src.query_generation.services.question_generator.embedding')
    def test_find_similar_questions_threshold_filtering(self, mock_embedding):
        """Test that threshold filters out low similarity questions."""
        # Mock batch embedding response with different similarity scores
        query_vector = [1.0, 0.0, 0.0, 0.0, 0.0]
        high_sim_vector = [0.95, 0.05, 0.0, 0.0, 0.0]  # ~0.99 similarity
        medium_sim_vector = [0.5, 0.5, 0.0, 0.0, 0.0]  # ~0.707 similarity
        low_sim_vector = [0.0, 1.0, 0.0, 0.0, 0.0]     # 0.0 similarity

        mock_embedding.return_value.data = [
            {"embedding": query_vector},       # Query
            {"embedding": high_sim_vector},    # Candidate 1 - high
            {"embedding": medium_sim_vector},  # Candidate 2 - medium
            {"embedding": low_sim_vector}      # Candidate 3 - low
        ]

        query_text = "What are the AI risks?"
        candidate_texts = [
            (1, "What are the risks of AI?"),  # High similarity
            (2, "How does machine learning work?"),  # Medium similarity
            (3, "What is the weather today?")  # Low similarity
        ]

        # Set threshold to 0.6 - should exclude the weather question
        results = find_similar_questions(query_text, candidate_texts, threshold=0.6)

        # Should only return questions above threshold
        question_ids = [r[0] for r in results]
        assert 1 in question_ids
        assert 2 in question_ids
        assert 3 not in question_ids

    @patch('src.query_generation.services.question_generator.embedding')
    def test_find_similar_questions_sorted_by_score(self, mock_embedding):
        """Test that results are sorted by similarity score descending."""
        # Mock batch embedding response
        query_vector = [1.0, 0.0, 0.0]
        high_sim_vector = [0.9, 0.1, 0.0]    # ~0.99 similarity
        medium_sim_vector = [0.7, 0.3, 0.0]  # ~0.94 similarity
        low_sim_vector = [0.5, 0.5, 0.0]     # ~0.85 similarity

        mock_embedding.return_value.data = [
            {"embedding": query_vector},       # Query
            {"embedding": low_sim_vector},     # Candidate 1 - low
            {"embedding": high_sim_vector},    # Candidate 2 - high
            {"embedding": medium_sim_vector}   # Candidate 3 - medium
        ]

        query_text = "Query question"
        candidate_texts = [
            (1, "Low similarity"),
            (2, "High similarity"),
            (3, "Medium similarity")
        ]

        results = find_similar_questions(query_text, candidate_texts, threshold=0.7)

        # Results should be sorted by score descending
        scores = [r[1] for r in results]
        assert scores == sorted(scores, reverse=True)
        # First result should be the "high similarity" question
        assert results[0][0] == 2

    def test_find_similar_questions_empty_candidates(self):
        """Test finding similar questions with no candidates returns empty list."""
        query_text = "What is AI?"
        candidate_texts = []

        results = find_similar_questions(query_text, candidate_texts, threshold=0.7)

        assert results == []

    @patch('src.query_generation.services.question_generator.embedding')
    def test_find_similar_questions_handles_embedding_error(self, mock_embedding):
        """Test that embedding errors raise exception."""
        # Mock embedding API failure
        mock_embedding.side_effect = Exception("Embedding API error")

        query_text = "What is AI?"
        candidate_texts = [
            (1, "What is artificial intelligence?"),
            (2, "How does ML work?")
        ]

        # Should raise exception when embeddings fail
        with pytest.raises(Exception, match="Embedding API error"):
            find_similar_questions(query_text, candidate_texts, threshold=0.7)

    @patch('src.query_generation.services.question_generator.embedding')
    def test_find_similar_questions_batch_multiple_queries(self, mock_embedding):
        """Test batch processing with multiple queries using matrix multiplication."""
        # Mock batch embedding response for 2 queries + 3 candidates
        query1_vec = [1.0, 0.0, 0.0]
        query2_vec = [0.0, 1.0, 0.0]
        candidate1_vec = [0.9, 0.1, 0.0]  # Similar to query1
        candidate2_vec = [0.1, 0.9, 0.0]  # Similar to query2
        candidate3_vec = [0.0, 0.0, 1.0]  # Not similar to either

        mock_embedding.return_value.data = [
            {"embedding": query1_vec},      # Query 1
            {"embedding": query2_vec},      # Query 2
            {"embedding": candidate1_vec},  # Candidate 1
            {"embedding": candidate2_vec},  # Candidate 2
            {"embedding": candidate3_vec}   # Candidate 3
        ]

        query_texts = [
            (101, "What is AI?"),
            (102, "What is ML?")
        ]
        candidate_texts = [
            (1, "AI definition"),
            (2, "ML definition"),
            (3, "Weather forecast")
        ]

        results = find_similar_questions_batch(query_texts, candidate_texts, threshold=0.7)

        # Verify results structure
        assert len(results) == 2
        assert 101 in results
        assert 102 in results

        # Query 1 should be most similar to candidate 1
        assert len(results[101]) >= 1
        assert results[101][0][0] == 1  # Candidate 1 ID

        # Query 2 should be most similar to candidate 2
        assert len(results[102]) >= 1
        assert results[102][0][0] == 2  # Candidate 2 ID

        # Both queries should exclude candidate 3 (low similarity)
        query1_ids = [cid for cid, _ in results[101]]
        query2_ids = [cid for cid, _ in results[102]]
        assert 3 not in query1_ids
        assert 3 not in query2_ids
