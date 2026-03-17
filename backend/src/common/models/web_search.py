"""
Pydantic models for web search queries and results.
"""

from typing import List, Optional
from pydantic import BaseModel


class SearchQueryListOutput(BaseModel):
    """Structured output from LLM: list of search query strings."""
    queries: List[str]


class SearchResultSitelink(BaseModel):
    """A sitelink from a search result."""
    title: str
    link: str


class SearchResult(BaseModel):
    """A single organic search result from Serper API."""
    title: str
    snippet: str
    url: str
    position: Optional[int] = None
    date: Optional[str] = None
    sitelinks: Optional[List[SearchResultSitelink]] = None


class SearchResultsOutput(BaseModel):
    """Collection of search results."""
    results: List[SearchResult]
