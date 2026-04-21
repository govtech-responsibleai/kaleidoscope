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
│   │   ├── repositories/       # CRUD operations
│   │   └── migrations/         # Manual migration scripts
│   ├── llm/                    # LLM client and tracking
│   │   ├── client.py           # LiteLLM wrapper
│   │   ├── cost_tracker.py     # Cost tracking
│   │   └── instrumentation.py  # Phoenix instrumentation
│   ├── models/                 # Pydantic models
│   ├── prompts/                # Prompt templates (Jinja2)
│   └── services/               # Common services (document processing, rubric classification)
│
├── query_generation/           # Query generation module
│   ├── api/
│   │   └── routes/            # API endpoints (targets, jobs, personas, questions, KB)
│   └── services/              # Business logic
│
└── scoring/                    # Scoring module
    ├── api/
    │   └── routes/            # API endpoints (snapshots, answers, judges, qa_jobs, annotations, metrics)
    └── services/              # Business logic (judge scoring, claim processing, metrics)
```

## Authentication

The API uses JWT (JSON Web Token) authentication:

1. User logs in with username/password → receives a token
2. Token is sent with every request in the `Authorization: Bearer <token>` header
3. Server validates the token using `JWT_SECRET_KEY`
4. Token expires after 3 days → user must log in again

All endpoints (except `/auth/login`, `/health`, `/docs`) require a valid token.

### User Management

Only developers with the `ADMIN_API_KEY` can create users via the `/auth/admin/create-user` endpoint. This is separate from user authentication — regular users cannot create other users.

| Key | Purpose |
|-----|---------|
| `JWT_SECRET_KEY` | Signs and validates user tokens (never leaves server) |
| `ADMIN_API_KEY` | Authorizes user creation via API (sent over the network in `X-Admin-Key` header) |

Data is automatically scoped by user:

| User Type | Targets | Judges |
|-----------|---------|--------|
| **Admin** (`is_admin=true`) | Sees all targets | Sees all judges |
| **Regular User** | Only their own targets | Baseline judges + user's custom judges |


### Setup

1. **Generate secrets** (developers only, pre-deployment):
```bash
python scripts/generate_secret.py  # Run twice, once for each key
# Add to .env:
# JWT_SECRET_KEY=<generated-key>
# ADMIN_API_KEY=<another-generated-key>
```

2. **Create users** (developers only):
```bash
curl -X POST https://your-api/api/v1/auth/admin/create-user \
  -H "X-Admin-Key: <your-admin-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "pass123", "is_admin": false}'
```

To create admins: 

```bash
curl -X POST https://your-api/api/v1/auth/admin/create-user \
  -H "X-Admin-Key: <your-admin-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "pass123", "is_admin": true}'
```

### Using the API


All API calls require a valid token. First, login to get a token:

```bash
curl -sX POST http://localhost:8000/api/v1/auth/login \
  -d "username=<user>&password=<pass>"
```

Export the `access_token` for use in subsequent commands:

```bash
export TOKEN=<access_token from response>
```

> **Important:** All curl commands below require the Authorization header. Add this to every request:
> ```
> -H "Authorization: Bearer $TOKEN"
> ```

Tokens expire after 3 days.

---

## Setup

### Option 1: Docker (Recommended)

**Quick start:**

```bash
# 1. Set up environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY (for Gemini Flash) and SERPER_API_KEY (for web search)

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
# Edit .env with your settings (GEMINI_API_KEY, SERPER_API_KEY, JWT_SECRET_KEY, etc.)
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

The API uses **Google Gemini 2.5 Flash Lite** by default (`gemini/gemini-2.5-flash-lite`) via LiteLLM for text generation, and **Gemini Embedding 001** (`gemini/gemini-embedding-001`) for semantic similarity. **Web search** is powered by [Serper API](https://serper.dev) (requires `SERPER_API_KEY`).

### Default Model

The default model is defined in `src/common/config.py` and set to `gemini/gemini-2.5-flash-lite`.

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
  - `gemini/gemini-2.5-flash-lite` (default)
  - `gemini/gemini-2.5-flash`
  - `gemini/gemini-3.1-flash-lite-preview-global`
  - `gemini/gemini-3.1-pro-preview-global`

- **OpenAI (requires `OPENAI_API_KEY`):**
  - `gpt-5-nano`
  - `gpt-5-mini`
  - `gpt-5`

- **Azure OpenAI (requires `AZURE_AI_API_KEY` and `AZURE_AI_API_BASE`):**
  - `azure/gpt-5-nano-2025-08-07`
  - `azure/gpt-5-mini-2025-08-07`
  - `azure/gpt-5-2025-08-07`

- **Vertex AI Anthropic (requires `GEMINI_API_KEY`):**
  - `vertex_ai/claude-haiku-4-5`
  - `vertex_ai/claude-sonnet-4-5`
  - `vertex_ai/claude-opus-4-5`


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
GET    /api/v1/targets/{id}/personas/export   - Export personas (csv/json)
GET    /api/v1/targets/{id}/questions/export  - Export questions (csv/json)
GET    /api/v1/targets/snapshots/{snapshot_id}/export
                                        - Export snapshot results (supports ?include_evaluators=true for judge JSON)
GET    /api/v1/targets/{id}/export-all  - Export personas, questions, snapshots (+evaluator JSON) as ZIP
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
POST   /api/v1/personas                    - Manually create a persona (auto-approved)
POST   /api/v1/personas/{id}/approve      - Approve persona
POST   /api/v1/personas/{id}/reject       - Reject persona
POST   /api/v1/personas/bulk-approve      - Bulk approve personas
POST   /api/v1/personas/sample-nemotron   - Sample general personas from Nemotron dataset
```

Personas have a `source` field: `"generated"` (AI) or `"nemotron"` (sampled from NVIDIA's Nemotron-Personas-Singapore dataset).

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

### Answers

Generate answers for questions using external APIs (e.g., AIBots).

```
POST   /api/v1/answers                                          - Generate answer for a question
GET    /api/v1/answers/{id}                                     - Get answer by ID
DELETE /api/v1/answers/{id}                                     - Delete answer by ID
GET    /api/v1/question/{question_id}/answers                   - Get all answers for a question
GET    /api/v1/target/{target_id}/answers                       - Get all answers for a target
GET    /api/v1/snapshots/{snapshot_id}/answers                   - Get all answers for a snapshot
GET    /api/v1/answers/{answer_id}/scores/{judge_id}            - Get answer scores
GET    /api/v1/answers/{answer_id}/claims                       - Get answer claims with scores
PUT    /api/v1/answers/{answer_id}/selection                    - Toggle answer selection
PUT    /api/v1/answers/bulk-selection                           - Bulk update answer selection
PUT    /api/v1/snapshots/{snapshot_id}/answers/select-default   - Auto-select 20% of answers for annotation

# Label overrides (manual corrections to aggregated labels)
GET    /api/v1/answers/{answer_id}/label-override               - Get label override for an answer
PUT    /api/v1/answers/{answer_id}/label-override               - Create or update a label override
DELETE /api/v1/answers/{answer_id}/label-override               - Delete a label override (reset to judge consensus)
```

### Snapshots

Snapshots are versioned evaluation runs that capture answer sets for analysis. Snapshot responses include computed fields for tracking annotation progress: `answer_count`, `selected_for_annotation_count`, and `annotated_count`.

```
POST   /api/v1/snapshots                                                - Create snapshot
GET    /api/v1/targets/{target_id}/snapshots                            - List snapshots for target
GET    /api/v1/snapshots/{snapshot_id}                                  - Get snapshot details (includes computed counts)
PUT    /api/v1/snapshots/{snapshot_id}                                  - Update snapshot name/description
DELETE /api/v1/snapshots/{snapshot_id}                                  - Delete snapshot
GET    /api/v1/snapshots/{snapshot_id}/stats                            - Get snapshot statistics
GET    /api/v1/snapshots/{snapshot_id}/questions/approved/without-answers  - Get approved questions without answers for judge
GET    /api/v1/snapshots/{snapshot_id}/questions/approved/without-scores   - Get approved questions without scores for judge
```

### Judges

Judges are LLM-based evaluators that assess answer quality. Two evaluation types are supported:

- **Claim-based**: Extracts claims from answers, evaluates each claim, then aggregates to overall label
- **Response-level**: Evaluates the entire answer holistically in a single LLM call

Judges are scoped either to a rubric (`rubric_id=<target_rubric.id>`) or to the global default pool (`rubric_id=NULL`) used for custom rubric evaluation. Each rubric-scoped or global pool has one recommended baseline judge plus additional comparison judges.

```
GET    /api/v1/judges                                 - List all judges
POST   /api/v1/judges                                 - Create custom judge
GET    /api/v1/judges/baseline?rubric_id={rubric_id} - Get baseline judge for a rubric
GET    /api/v1/judges/available-models                - List available LLM models
GET    /api/v1/judges/by-rubric/{rubric_id}           - Get judges for a rubric
GET    /api/v1/judges/{judge_id}                      - Get judge details
PUT    /api/v1/judges/{judge_id}                      - Update judge (if editable)
DELETE /api/v1/judges/{judge_id}                      - Delete judge (if editable)
```

### Custom Rubrics

Define custom evaluation criteria per target beyond accuracy (e.g., relevance, tone, helpfulness). Each rubric has a set of options the judge can choose from.

```
GET    /api/v1/targets/{target_id}/rubrics             - List all rubrics for target
POST   /api/v1/targets/{target_id}/rubrics             - Create a rubric
PUT    /api/v1/targets/{target_id}/rubrics/{rubric_id} - Update a rubric
DELETE /api/v1/targets/{target_id}/rubrics/{rubric_id} - Delete a rubric
```

Fixed and preset rubrics get seeded rubric-scoped judges automatically. Custom rubrics use the global default judge pool unless users add rubric-specific custom judges.

### QA Jobs

QA Jobs orchestrate the automated scoring pipeline:

1. **Generate Answer**: Call target application API to get answer
2. **Extract Claims**: Split answer into sentences, check if checkworthy (claim-based only)
3. **Score Answer**: Use judge LLM to evaluate accuracy

```
POST   /api/v1/snapshots/{snapshot_id}/qa-jobs/start         - Start accuracy QA jobs (async)
POST   /api/v1/snapshots/{snapshot_id}/rubric-qa-jobs/start  - Start rubric evaluation jobs (async)
POST   /api/v1/qa-jobs/pause                                 - Pause running jobs
GET    /api/v1/snapshots/{snapshot_id}/qa-jobs               - List QA jobs for snapshot
GET    /api/v1/qa-jobs/{job_id}                              - Get job details with costs
```

### Annotations

Manual annotations allow humans to label answers for judge validation. Accuracy annotations use a boolean label (accurate/inaccurate), while rubric annotations select from the rubric's defined options.

```
# Accuracy annotations
POST   /api/v1/annotations                                       - Create single annotation
POST   /api/v1/annotations/bulk                                  - Bulk create annotations
GET    /api/v1/snapshots/{snapshot_id}/annotations               - List annotations for snapshot
GET    /api/v1/snapshots/{snapshot_id}/annotations/completion-status  - Check completion progress
GET    /api/v1/answers/{answer_id}/annotations                   - Get annotation for answer
GET    /api/v1/annotations/{annotation_id}                       - Get annotation by ID
PUT    /api/v1/annotations/{annotation_id}                       - Update annotation
DELETE /api/v1/annotations/{annotation_id}                       - Delete annotation

# Rubric annotations
GET    /api/v1/answers/{answer_id}/rubric-annotations            - Get all rubric annotations for an answer
PUT    /api/v1/answers/{answer_id}/rubric-annotations/{rubric_id} - Upsert a rubric annotation

# Rubric scores (LLM judge results)
GET    /api/v1/answers/{answer_id}/rubric-scores?rubric_id={id}  - Get judge scores for an answer+rubric
```

### Metrics

Calculate judge performance and export results.

```
# Accuracy metrics
GET    /api/v1/snapshots/{snapshot_id}/judges/{judge_id}/alignment   - Calculate judge alignment (F1, precision, recall, accuracy)
GET    /api/v1/snapshots/{snapshot_id}/judges/{judge_id}/accuracy    - Calculate target accuracy per judge
GET    /api/v1/snapshots/{snapshot_id}/results                       - Get aggregated results with majority vote
POST   /api/v1/snapshots/{snapshot_id}/export                        - Export results as CSV
GET    /api/v1/targets/{target_id}/snapshot-metrics                  - Get aggregated metrics for all snapshots of a target

# Rubric metrics
GET    /api/v1/snapshots/{snapshot_id}/judges/{judge_id}/rubrics/{rubric_id}/alignment  - Rubric judge alignment (F1 against human annotations)
GET    /api/v1/snapshots/{snapshot_id}/judges/{judge_id}/rubrics/{rubric_id}/accuracy   - Rubric judge accuracy (% best option)
GET    /api/v1/targets/{target_id}/rubric-snapshot-metrics?snapshot_id={id}             - Aggregated rubric metrics for a snapshot
```

## End-to-End Evaluation Workflow

This section demonstrates the complete evaluation pipeline from target creation through final metrics export.

---

### Phase 1: Setup

#### 1.1 Create Target

```bash
curl -X POST http://localhost:8000/api/v1/targets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "RAI Target",
    "agency": "GovTech Singapore",
    "purpose": "Provide responsible AI guidance",
    "target_users": "Government officers",
    "api_endpoint": "https://api.uat.aibots.gov.sg/v1.0/api",
    "endpoint_type": "aibots",
    "endpoint_config": {"api_key": "your_aibots_api_key"}
  }' | jq
```

**Target fields:**
- `name` (required): Name of the target application
- `agency`: Agency owning the target
- `purpose`: Purpose of the target application
- `target_users`: Expected target users
- `api_endpoint`: Base URL for the API (required for answer generation)
- `endpoint_type`: Type of endpoint (`aibots` currently supported)
- `endpoint_config`: Type-specific config (for `aibots`: `{"api_key": "..."}`)

#### 1.2 Upload Knowledge Base Documents

Upload documents that will be used to generate in-KB vs out-of-KB questions:

```bash
# Upload a PDF document
curl -X POST http://localhost:8000/api/v1/targets/1/knowledge-base/upload \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/document.pdf" | jq

# Upload a text document
curl -X POST http://localhost:8000/api/v1/targets/1/knowledge-base/upload \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/guide.md" | jq

# List all KB documents for a target
curl http://localhost:8000/api/v1/targets/1/knowledge-base/documents | jq

# Get compiled KB text (for review)
curl http://localhost:8000/api/v1/targets/1/knowledge-base/text | jq
```

---

### Phase 2: Persona Generation

#### 2.1 Generate Personas

```bash
curl -X POST http://localhost:8000/api/v1/jobs/personas \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": 1,
    "count_requested": 5,
    "model_used": "gemini/gemini-2.5-flash-lite"
  }' | jq
```

#### 2.2 Check Job Status

```bash
curl http://localhost:8000/api/v1/jobs/1 | jq
```

Persona generation includes **Singapore contextualisation** (demographics, challenges, multicultural context) and **vague audience handling** (interprets "everyone" or "all officers" in context of the target application).

#### 2.3 List Generated Personas

```bash
curl http://localhost:8000/api/v1/jobs/1/personas | jq
```

#### 2.4 Manually Create Persona

```bash
curl -X POST http://localhost:8000/api/v1/personas \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": 1,
    "title": "Senior HR Officer",
    "info": "10 years experience in government HR",
    "style": "formal",
    "use_case": "Policy clarification"
  }' | jq
```

#### 2.5 Alternative: Sample General Personas (Nemotron)

Instead of LLM generation, sample from NVIDIA's [Nemotron-Personas-Singapore](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Singapore) dataset (~148K personas):

```bash
curl -X POST http://localhost:8000/api/v1/personas/sample-nemotron \
  -H "Content-Type: application/json" \
  -d '{"target_id": 1, "n": 5}' | jq
```

First call downloads and caches the dataset; subsequent calls are instant. Duplicate titles are auto-suffixed.

#### 2.6 Approve Personas

```bash
# Approve individual persona
curl -X POST http://localhost:8000/api/v1/personas/1/approve | jq

# Or bulk approve
curl -X POST http://localhost:8000/api/v1/personas/bulk-approve \
  -H "Content-Type: application/json" \
  -d '{"persona_ids": [1, 2, 3, 4, 5]}' | jq
```

---

### Phase 3: Question Generation

#### 3.1 Generate Questions

Questions are generated with **type** (typical/edge) and **scope** (in_kb/out_kb) attributes based on uploaded KB documents. The generation pipeline includes:

- **Input Style**: Controls question tone/verbosity — `brief` (terse, slang), `regular` (natural language, default), or `detailed` (professional, complete sentences)
- **Web Search Context**: Automatically queries the web (via Serper API) for contextual information about the target agency/domain, and feeds results into the prompt for more realistic, grounded questions
- **Singapore Contextualisation**: Prompts are tailored to produce questions relevant to Singapore government agencies and policies
- **Deduplication**: New questions are checked against existing questions in the current batch to reduce duplicates

**Note:** Question generation runs asynchronously. The endpoint returns immediately with `status="running"`.

```bash
# Generate questions for all approved personas (async)
curl -X POST http://localhost:8000/api/v1/jobs/questions \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": 1,
    "count_requested": 1,
    "model_used": "gemini/gemini-2.5-flash-lite",
    "input_style": "regular"
  }' | jq
# Returns immediately with status="running" and job_id

# Or generate questions for specific personas with brief style
curl -X POST http://localhost:8000/api/v1/jobs/questions \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": 1,
    "count_requested": 10,
    "model_used": "gemini/gemini-2.5-flash-lite",
    "input_style": "brief",
    "persona_ids": [1, 3, 5]
  }' | jq
```

#### 3.2 Check Job Completion

```bash
curl http://localhost:8000/api/v1/jobs/2 | jq
# Returns job with status: "running", "completed", or "failed"
```

#### 3.3 Review and Approve Questions

```bash
# List questions from job
curl http://localhost:8000/api/v1/jobs/2/questions | jq

# Approve individual question
curl -X POST http://localhost:8000/api/v1/questions/1/approve | jq

# Or bulk approve
curl -X POST http://localhost:8000/api/v1/questions/bulk-approve \
  -H "Content-Type: application/json" \
  -d '{"question_ids": [1, 2, 3, 4]}' | jq
```

#### 3.4 Find Similar Questions (Optional)

Find semantically similar questions using **Gemini Embedding 001** for deduplication.

```bash
curl -X POST http://localhost:8000/api/v1/questions/similar \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": 1,
    "question_ids": [5, 12, 18],
    "similarity_threshold": 0.75
  }' | jq
```

**Performance:** Uses batch processing with matrix multiplication (~10x faster for large sets).

---

### Phase 4: Create Snapshot & Generate Answers

#### 4.1 Create Snapshot

Snapshots are versioned evaluation runs that capture answer sets.

```bash
curl -X POST http://localhost:8000/api/v1/snapshots \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": 1,
    "name": "Baseline Eval",
    "description": "Initial evaluation of RAI target"
  }' | jq
```

---

### Phase 5: Automated Scoring (QA Jobs)

#### 5.1 Start QA Jobs

Each job runs through the full pipeline: **Generate Answer → Extract Claims → Score Answer**

```bash
# Start QA jobs for questions 1-5 with baseline judge
curl -X POST http://localhost:8000/api/v1/snapshots/1/qa-jobs/start \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot_id": 1,
    "judge_id": 1,
    "question_ids": [1, 2, 3, 4],
    "is_scoring": false
  }' | jq
```

**Job Stages:**
- `starting` → `generating_answers` → `processing_answers` → `scoring_answers` → `completed`

#### 5.2 Monitor Job Progress

```bash
# Check individual job status
curl http://localhost:8000/api/v1/qa-jobs/1 | jq

# List all jobs for snapshot
curl http://localhost:8000/api/v1/snapshots/2/qa-jobs | jq
```

#### 5.3 Pause/Resume Jobs (Optional)

```bash
# Pause running jobs
curl -X POST http://localhost:8000/api/v1/qa-jobs/pause \
  -H "Content-Type: application/json" \
  -d '{"job_ids": [1, 2, 3]}' | jq

# Resume by starting again with same parameters
curl -X POST http://localhost:8000/api/v1/snapshots/1/qa-jobs/start \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot_id": 1,
    "judge_id": 1,
    "job_ids": [1, 2, 3],
    "is_scoring": false
  }' | jq
```

Failed stages are retried when resumed.

---

### Phase 6: Human Annotations

For judge validation, manually annotate a subset of answers.

#### 6.1 Select Answers for Annotation

Before annotating, you must select which answers to annotate. You can auto-select 20% or manually select specific answers.

```bash
# Option 1: Auto-select 20% of answers (minimum 1)
curl -X POST http://localhost:8000/api/v1/snapshots/1/answers/select-default | jq

# Option 2: Manually select specific answers
# Toggle single answer
curl -X PUT http://localhost:8000/api/v1/answers/1/selection | jq

# Bulk select multiple answers
curl -X POST http://localhost:8000/api/v1/answers/bulk-selection \
  -H "Content-Type: application/json" \
  -d '{
    "selections": [
      {"answer_id": 1, "is_selected": true}
    ]
  }' | jq
```

#### 6.2 Create Annotations

```bash
# Bulk create annotations for selected answers
curl -X POST http://localhost:8000/api/v1/annotations/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "annotations": [
      {"answer_id": 1, "label": true, "notes": "Accurate response"},
      {"answer_id": 2, "label": false, "notes": "Contains hallucination"},
      {"answer_id": 3, "label": true, "notes": "Correct but incomplete"}
    ]
  }' | jq
```

#### 6.3 Check Annotation Progress

```bash
curl http://localhost:8000/api/v1/snapshots/1/annotations/completion-status | jq
```

Returns:
```json
{
  "total_selected": 10,
  "total_selected_and_annotated": 3,
  "is_complete": false,
  "completion_percentage": 30.0
}
```

---

### Phase 7: Metrics & Export

#### 7.1 Calculate Judge Alignment

Compares judge scores to human annotations using F1, precision, recall, and accuracy.

```bash
curl http://localhost:8000/api/v1/snapshots/1/judges/1/alignment | jq
```

Returns:
```json
{
  "f1": 0.857,
  "precision": 0.900,
  "recall": 0.818,
  "accuracy": 0.850,
  "sample_count": 20
}
```

#### 7.2 Calculate Target Accuracy

Based on judge scores across all answers.

```bash
curl http://localhost:8000/api/v1/snapshots/1/judges/1/accuracy | jq
```

Returns:
```json
{
  "accuracy": 0.730,
  "total_answers": 100,
  "accurate_count": 73
}
```

#### 7.3 Get Aggregated Results

Returns majority-vote labels across all judges with individual breakdowns.

```bash
curl http://localhost:8000/api/v1/snapshots/1/results | jq
```

#### 7.4 Export Personas and Questions

```bash
# Export personas as CSV (default)
curl "http://localhost:8000/api/v1/targets/1/personas/export" \
  --output target_1_personas.csv

# Export personas as JSON
curl "http://localhost:8000/api/v1/targets/1/personas/export?format=json" | jq

# Export questions as CSV (default)
curl "http://localhost:8000/api/v1/targets/1/questions/export" \
  --output target_1_questions.csv

# Export questions as JSON
curl "http://localhost:8000/api/v1/targets/1/questions/export?format=json" | jq
```

#### 7.5 Export Results as CSV

```bash
# Standard CSV export (frontend default)
curl "http://localhost:8000/api/v1/targets/snapshots/1/export" \
  --output snapshot_1_results.csv

# Include evaluator metrics & raw judge scores (returns ZIP with CSV + JSON)
curl "http://localhost:8000/api/v1/targets/snapshots/1/export?include_evaluators=true" \
  --output snapshot_1_results_with_judges.zip

# Export everything (personas, questions, snapshots, evaluator JSON) for a target
curl "http://localhost:8000/api/v1/targets/8/export-all" \
  --output target_1_export.zip
```

The CSV contains Question | Answer | Human Label | Aggregated Accuracy | Metadata (per-judge breakdown).  
When `include_evaluators=true`, the zip also contains `snapshot_1_evaluators.json` with judge accuracy/alignment stats and every `AnswerScore`.

#### 7.6 Get Snapshot Metrics (Target-Level)

Returns aggregated performance metrics across all snapshots for a target, useful for tracking improvements over time.

```bash
curl http://localhost:8000/api/v1/targets/1/snapshot-metrics | jq
```

Returns:
```json
[
  {
    "snapshot_id": 1,
    "snapshot_name": "v1.0",
    "created_at": "2025-01-15T10:30:00Z",
    "aggregated_accuracy": 0.73,
    "total_answers": 100,
    "accurate_count": 73,
    "inaccurate_count": 20,
    "pending_count": 7,
    "edited_count": 2,
    "judge_alignment_range": {"min": 0.85, "max": 0.92},
    "aligned_judges": [
      {"judge_id": 1, "name": "Baseline Judge", "f1": 0.85}
    ]
  }
]
```

**Metrics explanation:**
- `aggregated_accuracy`: Overall accuracy based on majority vote across aligned judges
- `accurate_count` / `inaccurate_count` / `pending_count`: Breakdown by aggregated label
- `edited_count`: Answers with manual label overrides
- `judge_alignment_range`: F1 score range of aligned judges (F1 ≥ 0.5)
- `aligned_judges`: List of judges that met the alignment threshold

## Observability with Phoenix

If `PHOENIX_COLLECTOR_ENDPOINT` is configured, all LLM calls are automatically tracked. 
Note: when running in Docker, use `host.docker.internal` instead of `localhost` to reach Phoenix on your host machine.

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

**Manual Migration Scripts** (in `src/common/database/migrations/`):

```bash
# Run migrations inside Docker container (recommended)
docker exec -it kaleidoscope-api python -m src.common.database.migrations.<migration_name>

# Or if running locally with correct DATABASE_URL in .env
python -m src.common.database.migrations.<migration_name>

# Rollback a migration
docker exec -it kaleidoscope-api python -m src.common.database.migrations.<migration_name> --downgrade
```

**Alembic (alternative)**:
```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Airbase Deployment

### Prerequisites
- [Airbase CLI](https://console.v2.airbase.sg/docs/get-started/installation) installed and configured

### Setup

1. Build and deploy:
```bash
export TEAM_HANDLE=<your-team-handle>
export API_PROJECT_HANDLE=<your-project-handle>
export FE_PROJECT_HANDLE=<your-project-handle>

# Build the Docker image
docker build --platform linux/amd64 -f Dockerfile-airbase -t airbase-kaleidoscope-api .

# Deploy to Airbase
airbase container deploy \
--project $TEAM_HANDLE/$API_PROJECT_HANDLE \
--image airbase-kaleidoscope-api 
```

2. Create `.env.default` with your secrets (same variables as `.env`):
```env
DATABASE_URL=<your-database-url>
GEMINI_API_KEY=<your-api-key>
# ... other secrets from .env
```

To get `DATABASE_URL`: Login via TechPass to [dbslicer](https://dbslicer.app.tc1.airbase.sg) and copy your database connection strings (e.g. `DATABASE_URL`, `DATABASE_HOST`, etc.).

For help, join the `#airbase-v2` Slack channel.
