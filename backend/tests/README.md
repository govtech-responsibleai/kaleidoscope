# Tests

## Setup

Install test dependencies:

```bash
pip install -r requirements.txt
```

## Running Tests

### Run all tests

```bash
pytest
```

### Run only unit tests

```bash
pytest -m unit
```

### Run only integration tests

```bash
pytest -m integration
```

### Run with verbose output

```bash
pytest -v
```

### Run specific test file

```bash
pytest tests/unit/test_persona_generator.py
pytest tests/integration/test_persona_api.py
```

### Run specific test

```bash
pytest tests/unit/test_persona_generator.py::TestPersonaGenerator::test_init
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests
│   └── test_persona_generator.py
└── integration/             # Integration tests
    └── test_persona_api.py
```

## Test Coverage

**Unit Tests** (`test_persona_generator.py`):
- PersonaGenerator initialization
- Prompt rendering with/without approved personas
- Response parsing (list/dict formats, invalid JSON)
- Saving personas to database
- Job status updates
- Error handling

**Integration Tests** (`test_persona_api.py`):
- End-to-end persona generation flow
- API error handling (target not found)

## Fixtures

Common fixtures in `conftest.py`:
- `test_db` - In-memory SQLite database
- `test_client` - FastAPI test client
- `sample_target` - Sample target for testing
- `sample_job` - Sample job for testing
- `sample_personas` - Sample personas for testing
- `mock_llm_response` - Mock LLM response
