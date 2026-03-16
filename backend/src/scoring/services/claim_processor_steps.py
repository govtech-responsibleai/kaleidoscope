"""
Modular pipeline steps for claim processing.

Two step types:
- ClaimTransform: reshapes the list of claims (split, merge, reorder)
- ClaimFilter: per-claim decision to skip LLM checkworthy call

To add a new step:
1. Subclass ClaimTransform or ClaimFilter
2. Implement the required method
3. Add your step to the pipeline lists in ClaimProcessor.__init__
"""

import re
import logging
from abc import ABC, abstractmethod
from typing import List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base classes
# ---------------------------------------------------------------------------


class ClaimTransform(ABC):
    """Reshapes a list of claims. Runs after NLTK tokenization."""

    @abstractmethod
    def transform(self, claims: List[str]) -> List[str]:
        """
        Transform the list of claims.

        Args:
            claims: List of claim strings

        Returns:
            Transformed list of claim strings
        """
        ...


class ClaimFilter(ABC):
    """Per-claim filter that decides whether to skip the LLM checkworthy call.

    Returns False to mark not-checkworthy (skip LLM), or None to defer to LLM.
    """

    @abstractmethod
    def check(self, claim_text: str) -> Optional[bool]:
        """
        Check if a claim should skip the LLM checkworthy call.

        Args:
            claim_text: The claim text to evaluate

        Returns:
            False if definitely not checkworthy (skip LLM).
            None to defer to the LLM.
        """
        ...

    @property
    def name(self) -> str:
        """Human-readable name for logging."""
        return self.__class__.__name__


# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------


class ClaimSplitNewlines(ClaimTransform):
    """Split claims containing newlines, keeping the newline with the first part."""

    def transform(self, claims: List[str]) -> List[str]:
        result = []
        for claim in claims:
            if "\n" in claim:
                parts = claim.split("\n")
                for part in parts[:-1]:
                    result.append(part + "\n")
                if parts[-1]:
                    result.append(parts[-1])
            else:
                result.append(claim)
        return result


class ClaimMergeCodeBlocks(ClaimTransform):
    """Merge claims that belong to the same fenced code block (e.g. mermaid, citations).

    NLTK may split a fenced code block across multiple claims. This step
    detects partial fences and merges consecutive claims back together so
    the entire block becomes a single claim.
    """

    _FENCE_PATTERN = re.compile(r"^(`{3,})", re.MULTILINE)

    def transform(self, claims: List[str]) -> List[str]:
        result: List[str] = []
        inside_block = False
        fence_marker: str = ""

        for claim in claims:
            if not inside_block:
                match = self._FENCE_PATTERN.search(claim)
                if match:
                    fence_marker = match.group(1)
                    # Check if same claim also closes the block
                    rest = claim[match.end():]
                    if fence_marker in rest:
                        # Self-contained block
                        result.append(claim)
                    else:
                        inside_block = True
                        result.append(claim)
                else:
                    result.append(claim)
            else:
                # Inside a code block — merge into the last claim
                result[-1] += claim
                if fence_marker in claim:
                    inside_block = False

        return result


class ClaimShiftBracketGroups(ClaimTransform):
    """Shift leading complete bracket groups from a claim to the previous claim."""

    _OPENING = frozenset("([{<")
    _CLOSING = frozenset(")]}>")

    def transform(self, claims: List[str]) -> List[str]:
        for i in range(1, len(claims)):
            bracket_content = self._find_leading_brackets(claims[i])
            if bracket_content:
                claims[i - 1] += bracket_content
                claims[i] = claims[i][len(bracket_content):]
        return claims

    def _find_leading_brackets(self, text: str) -> str:
        pos = 0
        shifted = ""
        while pos < len(text) and text[pos] in self._OPENING:
            depth = 0
            start = pos
            found = False
            for i in range(pos, len(text)):
                if text[i] in self._OPENING:
                    depth += 1
                elif text[i] in self._CLOSING:
                    depth -= 1
                    if depth == 0:
                        shifted += text[start : i + 1]
                        pos = i + 1
                        found = True
                        break
            if not found:
                break
        return shifted


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class ClaimShortFilter(ClaimFilter):
    """Mark very short claims as not checkworthy."""

    def __init__(self, min_length: int = 20):
        self.min_length = min_length

    def check(self, claim_text: str) -> Optional[bool]:
        if len(claim_text) < self.min_length:
            return False
        return None


class ClaimCitationFilter(ClaimFilter):
    """Mark citation references as not checkworthy."""

    _PATTERNS = [
        re.compile(r"Source\s+ID\s*:", re.IGNORECASE),
        re.compile(r"Chunk\s+Ref\s+ID\s*:", re.IGNORECASE),
        re.compile(r"^\s*\d+\.\s*Source\s+ID\s*:", re.IGNORECASE),
        re.compile(r"^\s*```citations", re.IGNORECASE),
    ]

    def check(self, claim_text: str) -> Optional[bool]:
        for pattern in self._PATTERNS:
            if pattern.search(claim_text):
                return False
        return None



