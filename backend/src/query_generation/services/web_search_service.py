"""
Web search service for gathering contextual information.

Uses an LLM to generate search queries based on target app context,
then executes them via Serper API to provide grounding context
for question generation (or other use cases).
"""

import logging
from typing import List, Optional

import httpx
from sqlalchemy.orm import Session

from src.common.config import get_settings
from src.common.llm import LLMClient, CostTracker
from src.common.prompts import render_template
from src.common.models.web_search import (
    SearchQueryListOutput,
    SearchResult,
    SearchResultSitelink,
)
from src.common.database.repositories import TargetRepository, WebDocumentRepository

logger = logging.getLogger(__name__)


class WebSearchService:
    """Service for gathering web search context using Serper API.

    Reusable across different parts of the app (question generation, scoring, etc.)
    by providing a different template_name for each use case.
    """

    def __init__(
        self,
        db: Session,
        target_id: int,
        cost_tracker: CostTracker,
        num_queries: int = 1,
        template_name: str = "web_search_queries_qngen.md",
    ):
        """
        Initialize web search service.

        Args:
            db: Database session
            target_id: Target ID to load context from
            cost_tracker: Cost tracker for LLM calls
            num_queries: Number of search queries to generate
            template_name: Prompt template used by the LLM to generate search
                queries. Override for different use cases (e.g. scoring).
        """
        self.db = db
        self.target_id = target_id
        self.cost_tracker = cost_tracker
        self.num_queries = num_queries
        self.template_name = template_name

        self.target = TargetRepository.get_by_id(db, target_id)
        if not self.target:
            raise ValueError(f"Target {target_id} not found")

        self.llm_client = LLMClient()
        self.settings = get_settings()

    def generate_search_queries(self) -> List[str]:
        """
        Use LLM to generate search queries based on target app context.

        Returns:
            List of search query strings
        """
        prompt = render_template(
            self.template_name,
            target_name=self.target.name,
            agency=self.target.agency or "Not specified",
            purpose=self.target.purpose or "Not specified",
            target_users=self.target.target_users or "General users",
            num_queries=self.num_queries,
        )

        query_list, metadata = self.llm_client.generate_structured(
            prompt=prompt,
            response_model=SearchQueryListOutput,
            temperature=1,
            max_tokens=300,
        )

        self.cost_tracker.add_call(metadata)

        logger.info(f"Generated {len(query_list.queries)} search queries for target {self.target_id}")
        return query_list.queries

    def execute_searches(self, queries: List[str]) -> List[SearchResult]:
        """
        Execute search queries via Serper API.

        Args:
            queries: List of search query strings

        Returns:
            List of SearchResult objects, deduplicated by URL
        """
        if not self.settings.serper_api_key:
            logger.warning("SERPER_API_KEY not set, skipping web search")
            return []

        results: List[SearchResult] = []
        seen_urls: set = set()

        with httpx.Client(timeout=10.0) as client:
            for query in queries:
                try:
                    response = client.post(
                        "https://google.serper.dev/search",
                        headers={
                            "X-API-KEY": self.settings.serper_api_key,
                            "Content-Type": "application/json",
                        },
                        json={"q": query, "gl": "sg", "num": 5},
                    )
                    response.raise_for_status()
                    data = response.json()

                    for item in data.get("organic", []):
                        url = item.get("link", "")
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)

                        sitelinks = None
                        if item.get("sitelinks"):
                            sitelinks = [
                                SearchResultSitelink(
                                    title=sl.get("title", ""),
                                    link=sl.get("link", ""),
                                )
                                for sl in item["sitelinks"]
                            ]

                        results.append(SearchResult(
                            title=item.get("title", ""),
                            snippet=item.get("snippet", ""),
                            url=url,
                            position=item.get("position"),
                            date=item.get("date"),
                            sitelinks=sitelinks,
                        ))

                except Exception as e:
                    logger.warning(f"Serper API call failed for query '{query}': {e}")
                    continue

        logger.info(f"Retrieved {len(results)} unique search results for target {self.target_id}")
        return results

    def get_search_context(self) -> str:
        """
        Generate search queries, execute them, save as WebDocument, and return formatted context.

        Returns:
            Formatted string of search results for prompt injection,
            or empty string if search fails or is unavailable.
        """
        try:
            queries = self.generate_search_queries()
            results = self.execute_searches(queries)

            if not results:
                return ""

            # Save as WebDocument (upsert: replace existing for this target)
            results_data = [result.model_dump() for result in results]
            document_data = {
                "search_queries": queries,
                "results": {"results": results_data},
            }
            WebDocumentRepository.upsert_for_target(
                self.db, self.target_id, document_data
            )

            # Use the repo's formatter to avoid duplicating formatting logic
            return WebDocumentRepository.get_compiled_context(
                self.db, self.target_id
            )

        except Exception as e:
            logger.error(f"Web search context generation failed: {e}", exc_info=True)
            return ""
