"""
Unit tests for QuestionGenerator service.
"""

import pytest
from unittest.mock import patch

from src.query_generation.services.question_generator import (
    cosine_similarity,
    get_question_embedding,
    find_similar_questions,
    find_similar_questions_batch
)


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
            model="gemini/text-embedding-004",
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
