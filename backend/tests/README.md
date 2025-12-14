# Tests

## Setup

```bash
pip install -r requirements.txt
```

## Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Verbose output
pytest -v

# Specific test file
pytest tests/unit/test_persona_generator.py

# With coverage report
pytest --cov=src --cov-report=html
# View: open htmlcov/index.html
```

## Test Structure

```
tests/
├── conftest.py                       # Shared fixtures
├── unit/                             # Unit tests
│   ├── test_persona_generator.py
│   ├── test_question_generator.py
│   ├── test_answer_generator.py
│   ├── test_claim_processor.py
│   ├── test_qa_job_processor.py
│   ├── test_judge_scoring.py
│   └── test_metrics_service.py
└── integration/                      # Integration tests
    ├── test_persona_api.py
    └── test_question_api.py
```

## Test Coverage

**Query Generation (Unit)**
- `test_persona_generator.py` - Persona generation, prompt rendering, response parsing
- `test_question_generator.py` - Question generation with type/scope, KB integration
- `test_answer_generator.py` - Answer generation from external APIs

**Scoring Pipeline (Unit)**
- `test_claim_processor.py` - Claim extraction (NLTK), checkworthy evaluation
- `test_qa_job_processor.py` - QA job pipeline orchestration, stage transitions
- `test_judge_scoring.py` - Claim-based & response-level scoring, cost tracking
- `test_metrics_service.py` - Judge alignment (F1, precision, recall), accuracy calculation

**API Integration**
- `test_persona_api.py` - End-to-end persona generation flow
- `test_question_api.py` - End-to-end question generation flow

## Fixtures

**Core**
- `test_db` / `test_db_factory` - In-memory SQLite database
- `test_client` - FastAPI test client with dependency overrides
- `sample_target` - Sample target with API config
- `sample_job` - Sample generation job

**Query Generation**
- `sample_personas` - Approved/pending personas
- `sample_question` - Approved question with type/scope
- `mock_llm_response` - Mock LLM response for generation

**Scoring**
- `sample_snapshot` - Snapshot for versioned evaluation
- `sample_answer` - Answer with multi-sentence content
- `sample_qa_job` - QA job with judge/answer/snapshot
- `sample_judge_claim_based` / `sample_judge_response_level` - Judge configurations
- `sample_claims` - Claims extracted from answer
- `sample_kb_documents` - Knowledge base documents
- `sample_annotations` - Human annotations (7 accurate, 3 inaccurate)
- `sample_answer_scores` - Judge scores for answers
