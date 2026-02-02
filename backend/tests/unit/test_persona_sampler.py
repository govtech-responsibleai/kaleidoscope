"""
Unit tests for PersonaSampler service.
"""

import pytest
from src.query_generation.services.persona_sampler import PersonaSampler, _deduplicate_title
from src.common.database.models import PersonaSourceEnum, StatusEnum


@pytest.mark.unit
class TestPersonaSampler:

    def test_deduplicate_title(self):
        assert _deduplicate_title("Alice", set()) == "Alice"
        assert _deduplicate_title("Alice", {"Alice"}) == "Alice (2)"
        assert _deduplicate_title("Alice", {"Alice", "Alice (2)"}) == "Alice (3)"

    def test_sample(self, test_db, sample_target):
        sampler = PersonaSampler(test_db, sample_target.id)
        personas = sampler.sample(1)

        assert len(personas) == 1
        p = personas[0]
        assert p.source == PersonaSourceEnum.nemotron
        assert p.job_id is None
        assert p.target_id == sample_target.id
        assert p.status == StatusEnum.pending
        assert p.title
        assert p.info
