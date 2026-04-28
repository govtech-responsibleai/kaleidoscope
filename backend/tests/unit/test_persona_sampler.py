"""
Unit tests for PersonaSampler service.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.query_generation.services.persona_sampler import (
    PersonaSampler,
    _deduplicate_title,
    _validate_dataset_name,
    _usa_style,
)
from src.common.database.models import PersonaSourceEnum, StatusEnum


def _make_fake_dataset(n=20):
    """Create a small fake dataset matching Nemotron-Personas-Singapore row format."""
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

    class FakeDataset:
        def __len__(self):
            return len(rows)

        def __getitem__(self, idx):
            return rows[idx]

        def shuffle(self, **_kwargs):
            return self

        def select(self, indices):
            return [rows[i] for i in indices]

    return FakeDataset()


_SG_DATASET = "nvidia/Nemotron-Personas-Singapore"


@pytest.mark.unit
class TestPersonaSampler:

    def test_deduplicate_title(self):
        assert _deduplicate_title("Alice", set()) == "Alice"
        assert _deduplicate_title("Alice", {"Alice"}) == "Alice (2)"
        assert _deduplicate_title("Alice", {"Alice", "Alice (2)"}) == "Alice (3)"

    @patch("src.query_generation.services.persona_sampler._load_nemotron_dataset")
    def test_sample(self, mock_load_dataset, test_db, sample_target):
        mock_load_dataset.return_value = (_make_fake_dataset(20), _SG_DATASET)

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

    # ------------------------------------------------------------------
    # New tests for configurable dataset behaviour
    # ------------------------------------------------------------------

    def test_validate_rejects_non_nvidia(self):
        with pytest.raises(ValueError, match="nvidia"):
            _validate_dataset_name("random/garbage")

    def test_validate_accepts_nemotron_dataset(self):
        # Should not raise
        _validate_dataset_name("nvidia/Nemotron-Personas-Singapore")
        _validate_dataset_name("nvidia/Nemotron-Personas-USA")

    @patch("src.query_generation.services.persona_sampler.load_dataset")
    @patch("src.query_generation.services.persona_sampler.get_settings")
    def test_load_fails_without_persona_column(self, mock_settings, mock_load_ds):
        mock_settings.return_value.nemotron_personas_dataset = _SG_DATASET
        fake_train = MagicMock()
        fake_train.column_names = ["sex", "age"]  # missing "persona"
        mock_load_ds.return_value = {"train": fake_train}

        import src.query_generation.services.persona_sampler as m
        original = m._nemotron_dataset
        m._nemotron_dataset = None
        m._nemotron_dataset_name = None
        try:
            from src.query_generation.services.persona_sampler import _load_nemotron_dataset
            with pytest.raises(RuntimeError, match="missing required column"):
                _load_nemotron_dataset()
        finally:
            m._nemotron_dataset = original

    def test_usa_template_renders(self):
        row = {
            "sex": "Female",
            "age": 30,
            "marital_status": "Single",
            "occupation": "Software Engineer",
            "city": "San Francisco",
            "state": "CA",
            "education_level": "Bachelor's degree",
        }
        style = _usa_style(row)
        assert "San Francisco" in style
        assert ", CA," in style
        assert "Bachelor's degree" in style

    @patch("src.query_generation.services.persona_sampler._load_nemotron_dataset")
    def test_title_alphabetic_fallback(self, mock_load, test_db, sample_target):
        # Non-Latin dataset (Korea) has no name extraction — uses Persona A/B/C.
        mock_load.return_value = (_make_fake_dataset(20), "nvidia/Nemotron-Personas-Korea")
        sampler = PersonaSampler(test_db, sample_target.id)
        personas = sampler.sample(3)
        assert [p.title for p in personas] == ["Persona A", "Persona B", "Persona C"]

    @patch("src.query_generation.services.persona_sampler._load_nemotron_dataset")
    def test_title_name_extraction_for_latin_datasets(self, mock_load, test_db, sample_target):
        # Singapore dataset uses regex name extraction from the persona field.
        mock_load.return_value = (_make_fake_dataset(1), _SG_DATASET)
        sampler = PersonaSampler(test_db, sample_target.id)
        personas = sampler.sample(1)
        # "Alice Smith 0 enjoys coding..." → regex extracts "Alice Smith"
        assert personas[0].title == "Alice Smith"
