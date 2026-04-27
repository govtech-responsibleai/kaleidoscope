"""
Unit tests for WebSearchService.

All tests mock the Serper API and LLM calls — no real API credits used.
"""

import pytest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

from src.common.models.web_search import SearchQueryListOutput, SearchResult
from src.common.database.models import WebDocument
from src.common.database.repositories import WebDocumentRepository
from src.query_generation.services.web_search_service import WebSearchService


# ============================================================================
# Mock Fixtures
# ============================================================================

MOCK_SERPER_RESPONSE = {
    "organic": [
        {
            "title": "Employment Act - Ministry of Manpower",
            "snippet": "The Employment Act covers all employees under a contract of service...",
            "link": "https://www.mom.gov.sg/employment-practices/employment-act",
            "position": 1,
        },
        {
            "title": "Annual Leave Entitlement - MOM",
            "snippet": "Employees are entitled to 7 days of annual leave after 3 months...",
            "link": "https://www.mom.gov.sg/employment-practices/leave/annual-leave",
            "position": 2,
        },
    ]
}

MOCK_SEARCH_QUERIES = SearchQueryListOutput(
    queries=[
        "Ministry of Manpower employment act Singapore",
        "Singapore annual leave entitlement",
    ]
)

MOCK_LLM_METADATA = {
    "prompt_tokens": 100,
    "completion_tokens": 30,
    "total_cost": 0.0001,
    "model": "litellm_proxy/gemini-3.1-flash-lite-preview-global",
}


def _make_service(test_db, sample_target):
    """Create a WebSearchService with mocked internals."""
    with patch.object(WebSearchService, "__init__", lambda self, *a, **kw: None):
        svc = WebSearchService.__new__(WebSearchService)
        svc.db = test_db
        svc.target_id = sample_target.id
        svc.target = sample_target
        svc.num_queries = 2
        svc.template_name = "web_search_queries_qngen.md"
        svc.cost_tracker = MagicMock()
        svc.llm_client = MagicMock()
        svc.serper_api_key = "test-api-key"
        return svc


# ============================================================================
# Tests
# ============================================================================

@pytest.mark.unit
class TestWebSearchService:
    """Unit tests for web search service."""

    def test_execute_searches_parses_serper_response(self, test_db, sample_target):
        """Serper API response is correctly parsed into SearchResult objects."""
        svc = _make_service(test_db, sample_target)

        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_SERPER_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch("src.query_generation.services.web_search_service.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(post=MagicMock(return_value=mock_response)))
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            results = svc.execute_searches(["test query"])

        assert len(results) == 2
        assert results[0].title == "Employment Act - Ministry of Manpower"
        assert results[0].url == "https://www.mom.gov.sg/employment-practices/employment-act"
        assert "Employment Act" in results[0].snippet

    def test_execute_searches_deduplicates_by_url(self, test_db, sample_target):
        """Duplicate URLs across queries are removed."""
        svc = _make_service(test_db, sample_target)

        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_SERPER_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch("src.query_generation.services.web_search_service.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(post=MagicMock(return_value=mock_response)))
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            # Two queries returning the same results
            results = svc.execute_searches(["query 1", "query 2"])

        assert len(results) == 2  # Not 4

    def test_execute_searches_handles_api_failure(self, test_db, sample_target):
        """API failure returns empty list without raising."""
        svc = _make_service(test_db, sample_target)

        with patch("src.query_generation.services.web_search_service.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.post.side_effect = Exception("API error")
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            results = svc.execute_searches(["test query"])

        assert results == []

    def test_execute_searches_skips_missing_api_key(self, test_db, sample_target):
        """Missing API key returns empty list with warning."""
        svc = _make_service(test_db, sample_target)
        svc.serper_api_key = None

        results = svc.execute_searches(["test query"])

        assert results == []

    def test_generate_search_queries(self, test_db, sample_target):
        """LLM generates search queries correctly."""
        svc = _make_service(test_db, sample_target)
        svc.llm_client.generate_structured.return_value = (MOCK_SEARCH_QUERIES, MOCK_LLM_METADATA)

        with patch("src.query_generation.services.web_search_service.render_template", return_value="mock prompt"):
            queries = svc.generate_search_queries()

        assert len(queries) == 2
        assert "Ministry of Manpower" in queries[0]
        svc.cost_tracker.add_call.assert_called_once_with(MOCK_LLM_METADATA)

    def test_get_search_context_formats_results_and_saves(self, test_db, sample_target):
        """Full pipeline returns formatted context string and saves WebDocument."""
        svc = _make_service(test_db, sample_target)
        svc.llm_client.generate_structured.return_value = (MOCK_SEARCH_QUERIES, MOCK_LLM_METADATA)

        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_SERPER_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch("src.query_generation.services.web_search_service.render_template", return_value="mock prompt"), \
             patch("src.query_generation.services.web_search_service.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(post=MagicMock(return_value=mock_response)))
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            context = svc.get_search_context()

        assert "Source: Employment Act - Ministry of Manpower" in context
        assert "URL: https://www.mom.gov.sg" in context
        assert "Content:" in context

        # Verify WebDocument was saved (upsert: one doc per target)
        docs = WebDocumentRepository.get_by_target(test_db, sample_target.id)
        assert len(docs) == 1
        assert docs[0].search_queries == MOCK_SEARCH_QUERIES.queries
        assert len(docs[0].results["results"]) == 2

    def test_get_search_context_returns_empty_on_failure(self, test_db, sample_target):
        """Full pipeline returns empty string when everything fails."""
        svc = _make_service(test_db, sample_target)
        svc.llm_client.generate_structured.side_effect = Exception("LLM error")

        with patch("src.query_generation.services.web_search_service.render_template", return_value="mock prompt"):
            context = svc.get_search_context()

        assert context == ""

    def test_get_compiled_context_returns_latest(self, test_db, sample_target):
        """get_compiled_context returns formatted context from the latest WebDocument."""
        # Create two WebDocuments — older and newer
        WebDocumentRepository.create(test_db, {
            "target_id": sample_target.id,
            "search_queries": ["old query"],
            "results": {"results": [
                {"title": "Old Result", "snippet": "Old snippet", "url": "https://old.com"},
            ]},
        })
        WebDocumentRepository.create(test_db, {
            "target_id": sample_target.id,
            "search_queries": ["new query"],
            "results": {"results": [
                {"title": "New Result", "snippet": "New snippet", "url": "https://new.com"},
            ]},
        })

        context = WebDocumentRepository.get_compiled_context(test_db, sample_target.id)

        assert "New Result" in context
        assert "https://new.com" in context
        # Should use latest, not old
        assert "Old Result" not in context

    def test_get_compiled_context_returns_empty_when_none(self, test_db, sample_target):
        """get_compiled_context returns empty string when no WebDocuments exist."""
        context = WebDocumentRepository.get_compiled_context(test_db, sample_target.id)
        assert context == ""
