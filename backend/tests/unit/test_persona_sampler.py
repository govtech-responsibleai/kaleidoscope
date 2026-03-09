"""
Unit tests for PersonaSampler service.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.query_generation.services.persona_sampler import PersonaSampler, _deduplicate_title
from src.common.database.models import PersonaSourceEnum, StatusEnum


def _make_fake_dataset(n=20):
    """Create a small fake dataset matching Nemotron row format."""
    rows = []
    for i in range(n):
        rows.append({
            "persona": f"Alice Smith {i} enjoys coding and building systems.",
            "sex": "Female",
            "age": str(25 + i),
            "marital_status": "Single",
            "occupation": f"Engineer_{i}",
            "industry": "Technology",
            "professional_persona": f"Professional info for persona {i}",
            "sports_persona": f"Sports info for persona {i}",
            "arts_persona": f"Arts info for persona {i}",
        })

    # Create a mock that behaves like a HuggingFace Dataset
    class FakeDataset:
        def __len__(self):
            return len(rows)

        def __getitem__(self, idx):
            return rows[idx]

        def shuffle(self, seed=None):
            return self

        def select(self, indices):
            return [rows[i] for i in indices]

    return FakeDataset()


@pytest.mark.unit
class TestPersonaSampler:

    def test_deduplicate_title(self):
        assert _deduplicate_title("Alice", set()) == "Alice"
        assert _deduplicate_title("Alice", {"Alice"}) == "Alice (2)"
        assert _deduplicate_title("Alice", {"Alice", "Alice (2)"}) == "Alice (3)"

    @patch("src.query_generation.services.persona_sampler._load_nemotron_dataset")
    def test_sample(self, mock_load_dataset, test_db, sample_target):
        mock_load_dataset.return_value = _make_fake_dataset(20)

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
