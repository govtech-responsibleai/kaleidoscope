# Kaleidoscope API

API service for LLM evaluation through query generation and scoring.

## Project Structure

```
src/
├── common/                      # Shared utilities
│   ├── config.py               # Configuration management
│   ├── database/               # Database layer
│   │   ├── connection.py       # SQLAlchemy setup
│   │   ├── models.py           # ORM models
│   │   └── repositories/       # CRUD operations
│   ├── llm/                    # LLM client and tracking
│   │   ├── client.py           # LiteLLM wrapper
│   │   ├── cost_tracker.py     # Cost tracking
│   │   └── instrumentation.py  # Phoenix instrumentation
│   ├── models/                 # Pydantic models
│   ├── prompts/                # Prompt templates (Jinja2)
│   └── services/               # Common services (document processing)
│
└── query_generation/           # Query generation module
    ├── api/
    │   ├── main.py            # FastAPI app
    │   └── routes/            # API endpoints
    └── services/              # Business logic
```

## Setup

### Option 1: Docker (Recommended)

**Quick start:**

```bash
# 1. Set up environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY (for Gemini Flash)

# 2. Start services
docker-compose up -d

# 3. View logs
docker-compose logs -f api
```

**Services:**
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Database: localhost:5432 (PostgreSQL)

See [DOCKER.md](DOCKER.md) for detailed Docker commands.

### Option 2: Local Development

**1. Install Dependencies:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**2. Configure Environment:**
```bash
cp .env.example .env
# Edit .env with your settings
```

**3. Setup Database:**
```bash
createdb kaleidoscope
```

**4. Run the API:**
```bash
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

API will be available at:
- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs

## LLM Configuration

The API uses **Google Gemini 2.0 Flash** by default (`gemini/gemini-2.0-flash`) via LiteLLM for text generation, and **Gemini Text Embedding 004** (`gemini/text-embedding-004`) for semantic similarity.

### Default Model

The default model is defined in `src/common/config.py` and set to `gemini/gemini-2.0-flash`.

### Overriding the Default Model

You can override the default model in two ways:

**1. Per-Request Override (Recommended for testing different models)**
```bash
curl -X POST http://localhost:8000/api/v1/jobs/personas \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": 1,
    "count_requested": 5,
    "model_used": "gpt-4o"
  }'
```

**2. Environment Variable Override (Recommended for deployment)**

Set `DEFAULT_LLM_MODEL` in your `.env` file:
```bash
# .env
DEFAULT_LLM_MODEL=gpt-4o
OPENAI_API_KEY=your_api_key
```

Or in `docker-compose.yml`:
```yaml
environment:
  DEFAULT_LLM_MODEL: gpt-4o
  OPENAI_API_KEY: ${OPENAI_API_KEY}
```

### Supported Models (via LiteLLM)

- **Gemini (requires `GEMINI_API_KEY`):**
  - `gemini/gemini-2.0-flash` (default, fast and cost-effective)
  - `gemini/gemini-1.5-flash`
  - `gemini/gemini-1.5-pro`

- **OpenAI (requires `OPENAI_API_KEY`):**
  - `gpt-4o-mini`
  - `gpt-4o`
  - `gpt-4-turbo`

- **Anthropic (requires `ANTHROPIC_API_KEY`):**
  - `claude-3-5-sonnet-20241022`
  - `claude-3-opus-20240229`


## API Endpoints

### Targets

```
POST   /api/v1/targets                    - Create target
GET    /api/v1/targets                    - List targets
GET    /api/v1/targets/{id}               - Get target
PUT    /api/v1/targets/{id}               - Update target
DELETE /api/v1/targets/{id}               - Delete target
GET    /api/v1/targets/{id}/stats         - Get stats
GET    /api/v1/targets/{id}/personas      - List personas for target
GET    /api/v1/targets/{id}/questions     - List questions for target
```

### Generation Jobs

```
# Create jobs
POST   /api/v1/jobs/personas              - Create persona generation job (synchronous)
POST   /api/v1/jobs/questions             - Create question generation job (async, with optional persona_ids)

# Retrieve jobs
GET    /api/v1/jobs?target_id={id}        - List jobs for target (query parameter)
GET    /api/v1/jobs/{id}                  - Get job details and status
GET    /api/v1/jobs/{id}/personas         - Get personas from job
GET    /api/v1/jobs/{id}/questions        - Get questions from job
```

### Personas

```
GET    /api/v1/personas/{id}              - Get persona
GET    /api/v1/personas/{id}/questions    - List questions for persona
PUT    /api/v1/personas/{id}              - Update persona
POST   /api/v1/personas/{id}/approve      - Approve persona
POST   /api/v1/personas/{id}/reject       - Reject persona
POST   /api/v1/personas/bulk-approve      - Bulk approve personas
```

### Questions

```
GET    /api/v1/questions/{id}             - Get question
PUT    /api/v1/questions/{id}             - Update question
POST   /api/v1/questions/{id}/approve     - Approve question
POST   /api/v1/questions/{id}/reject      - Reject question
POST   /api/v1/questions/bulk-approve     - Bulk approve questions
POST   /api/v1/questions/similar          - Find semantically similar questions (uses Gemini embeddings)
```

### Knowledge Base

```
POST   /api/v1/targets/{id}/knowledge-base/upload       - Upload and process KB document
GET    /api/v1/targets/{id}/knowledge-base/documents    - List all KB documents for target
GET    /api/v1/targets/{id}/knowledge-base/text         - Get compiled text from all KB documents
GET    /api/v1/knowledge-base/documents/{id}            - Get specific KB document with text
DELETE /api/v1/knowledge-base/documents/{id}            - Delete KB document
```

**Supported document formats:** PDF, DOCX, TXT, MD

## Usage Example

### 1. Create a Target

```bash
curl -X POST http://localhost:8000/api/v1/targets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "RAI Chatbot",
    "agency": "GovTech Singapore",
    "purpose": "Provide responsible AI guidance",
    "target_users": "Government officers",
    "api_endpoint": "https://api.example.com/chat",
    "knowledge_base_path": "/data/rai_docs"
  }'
```

### 2. Generate Personas

```bash
curl -X POST http://localhost:8000/api/v1/jobs/personas \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": 1,
    "count_requested": 5,
    "model_used": "gemini/gemini-2.0-flash"
  }'
```

### 3. Check Job Status

```bash
curl http://localhost:8000/api/v1/jobs/1
```

### 4. List Generated Personas

```bash
curl http://localhost:8000/api/v1/jobs/1/personas
```

### 5. Upload Knowledge Base Documents

Upload documents that will be used to generate in-KB vs out-of-KB questions:

```bash
# Upload a PDF document
curl -X POST http://localhost:8000/api/v1/targets/1/knowledge-base/upload \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/document.pdf"

# Upload a text document
curl -X POST http://localhost:8000/api/v1/targets/1/knowledge-base/upload \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/guide.md"

# List all KB documents for a target
curl http://localhost:8000/api/v1/targets/1/knowledge-base/documents

# Get compiled KB text (for review)
curl http://localhost:8000/api/v1/targets/1/knowledge-base/text
```

### 6. Approve a Persona

```bash
curl -X POST http://localhost:8000/api/v1/personas/1/approve
```

### 7. Generate Questions

**Note:** Question generation runs asynchronously. The endpoint returns immediately with `status="running"`. Use `GET /jobs/{id}` to check completion status.

Questions are generated with **type** (typical/edge) and **scope** (in_kb/out_kb) attributes. The system uses the uploaded knowledge base documents to generate questions both within and outside the KB scope.

```bash
# Generate questions for all approved personas (async)
curl -X POST http://localhost:8000/api/v1/jobs/questions \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": 1,
    "count_requested": 20,
    "model_used": "gemini/gemini-2.0-flash"
  }'
# Returns immediately with status="running" and job_id

# Or generate questions for specific personas (async)
curl -X POST http://localhost:8000/api/v1/jobs/questions \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": 1,
    "count_requested": 10,
    "model_used": "gemini/gemini-2.0-flash",
    "persona_ids": [1, 3, 5]
  }'

# Check job completion status
curl http://localhost:8000/api/v1/jobs/2
# Returns job with status: "running", "completed", or "failed"
```

### 8. List and Approve Questions

```bash
# List questions from job
curl http://localhost:8000/api/v1/jobs/2/questions

# Approve a question
curl -X POST http://localhost:8000/api/v1/questions/1/approve
```

### 9. Find Similar Questions

Find semantically similar questions using Gemini embeddings and cosine similarity. This feature uses **Gemini Text Embedding 004** (`gemini/text-embedding-004`) to generate embeddings and compares them using matrix multiplication for efficient batch processing.

**Key Features:**
- Uses Gemini text embeddings for semantic similarity
- Batch processing with matrix multiplication (highly efficient for multiple queries)
- Only compares against approved questions
- Configurable similarity threshold (default: 0.7)
- Returns results sorted by similarity score

```bash
# Find similar questions for a single question
curl -X POST http://localhost:8000/api/v1/questions/similar \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": 1,
    "question_ids": [5],
    "similarity_threshold": 0.7
  }'

# Find similar questions for multiple questions (batch processing)
curl -X POST http://localhost:8000/api/v1/questions/similar \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": 1,
    "question_ids": [5, 12, 18],
    "similarity_threshold": 0.75
  }'
```

**Example Response:**
```json
{
  "results": [
    {
      "query_question_id": 5,
      "similar_questions": [
        {
          "question_id": 23,
          "similarity_score": 0.92
        },
        {
          "question_id": 47,
          "similarity_score": 0.85
        }
      ]
    },
    {
      "query_question_id": 12,
      "similar_questions": [
        {
          "question_id": 31,
          "similarity_score": 0.88
        }
      ]
    }
  ]
}
```

**Performance:** For M query questions and N candidate questions:
- Makes 1 batch API call (instead of M separate calls)
- Computes M×N similarity matrix with single matrix multiplication
- ~10x faster for 10 queries with 100 candidates compared to sequential processing

## Observability with Phoenix

If `PHOENIX_COLLECTOR_ENDPOINT` is configured, all LLM calls are automatically tracked:

- Token counts (prompt, completion)
- Costs per call
- Request/response traces
- Performance metrics

View traces at your Phoenix dashboard (local or cloud).

## Development

### Running Tests

```bash
# Run all tests
pytest tests/

# Run only unit tests
pytest tests/unit/ -m unit

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_question_generator.py -v
```

**Test Coverage:**
- Question similarity functions (cosine similarity, embeddings, batch processing)
- Matrix multiplication optimization for finding similar questions

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Next Steps

- [x] Implement persona generation service logic
- [x] Implement question generation service logic
- [x] Add question similarity search using embeddings
- [x] Add unit tests for similarity functions
- [x] Add knowledge base document upload and processing
- [ ] Setup CI/CD
- [ ] Deploy to serverless (AWS Lambda, AWS RDS, etc.)
- [ ] Add scoring service (judge LLM evaluation)

## License

[Your License Here]
