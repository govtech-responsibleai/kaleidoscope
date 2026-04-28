<div align="center">

<img src=".github/kaleidoscope-logo-text-2.png" alt="Kaleidoscope"/>

Automated evaluation platform for AI-powered applications. Generate diverse test inputs and score the responses with LLM judges evaluated for reliability.

</div>

## 🤖 LLM Quickstart

For both setup and development, direct your agent to **[`AGENTS.md`](AGENTS.md)**.

## 👶 Human Quickstart

```bash
git clone https://github.com/govtech-responsibleai/kaleidoscope.git

cd kaleidoscope
cp .env.example .env          # add your LLM API key — see [Providers](#providers)

docker compose up -d   # log in: dev / dev
```

Head to `http://localhost:3000 ` to view your app.

A default admin user (`dev` / `dev`) is created on first startup. Add more users via the admin panel once logged in.

## 🔭 What can you do with Kaleidoscope?

<img src=".github/screenshots/target-setup.png" alt="target-setup" width="90%"/>

**Connect any LLM application** — point Kaleidoscope at any HTTP endpoint. Your chatbot, RAG pipeline, or custom API becomes the evaluation target with no code changes required.

<img src=".github/screenshots/rubrics.png" alt="rubrics" width="90%"/>

**Define custom rubrics** — write scoring criteria tailored to your use case. Evaluate dimensions like accuracy, tone, safety, or any domain-specific quality you care about.

<img src=".github/screenshots/question-generation-1.gif" width="90%"/>

**Generate diverse evaluation questions** — create user personas with Singapore contextualisation and generate realistic questions across types (typical/edge) and scopes (in-KB/out-of-KB).

<img src=".github/screenshots/annotations.png" alt="annotationsp" width="90%"/>

**Annotate with judge assistance** — claims and full responses are highlighted with judge reasoning. Human annotation in one click.

<img src=".github/screenshots/scoring2.png" alt="scoring" width="90%"/>

**Measure judge reliability** — evaluate answers with multiple LLM judges for comparison. Judge reliability is calculated from human annotations. Only reliable judges contribute to aggregated scores.


## 🔌 Providers

Kaleidoscope uses **LiteLLM** — any provider LiteLLM supports works out of the box. Add the relevant key to `.env` and you're set:

| Provider | Env var |
|----------|---------|
| Gemini | `GEMINI_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Azure OpenAI | `AZURE_API_KEY` + `AZURE_API_BASE` |
| AWS Bedrock | `AWS_BEARER_TOKEN_BEDROCK` |
| OpenRouter | `OPENROUTER_API_KEY` |
| Fireworks | `FIREWORKS_AI_API_KEY` |

Default models and the full list live in [`backend/src/common/llm/provider_catalog.yaml`](backend/src/common/llm/provider_catalog.yaml) — add your own there.

## 🛠️ Local Development

**Stack**: FastAPI + SQLAlchemy + LiteLLM (Python 3.13, uv) · Next.js 16 + React 19 + MUI v7 (TypeScript) · PostgreSQL

**Non-dev / full stack:**
```bash
git clone https://github.com/govtech-responsibleai/kaleidoscope.git
cd kaleidoscope
docker compose up -d
```

**Dev (recommended):**
```bash
docker compose up -d db backend   # db + backend in Docker
cd frontend && npm run dev         # frontend locally with hot reload
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

Docker reference: [DOCKER.md](DOCKER.md)  
Subsystem docs: [Backend](backend/README.md) | [Frontend](frontend/README.md)

## 🚀 Deployment

Configure your images in [`docker-compose.yml`](docker-compose.yml) and the [`backend/Dockerfile`](backend/Dockerfile) / [`frontend/Dockerfile`](frontend/Dockerfile).

**Before deploying to production** rotate the dev secrets to strong random values:

```bash
# Run twice — once for JWT_SECRET_KEY, once for ADMIN_API_KEY
cd backend && uv run python scripts/generate_secret.py
```

Set the outputs in `.env` or your deployment environment.

> **Nemotron dataset**: The first call to sample personas downloads the configured NVIDIA Nemotron dataset and caches it to `~/.cache/huggingface/`. Expect time and disk on first run — subsequent calls are instant. See [Customising personas](#customising-personas) to change the dataset.

## 🧑‍🤝‍🧑 Customising personas

Three options to customise personas for test case generation: 

1. AI personas 
2. Upload personas
3. Sample from NVIDIA's Nemotron Personas.

By default, the platform users [Nemotron-Personas-Singapore](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Singapore) (~148K rows). To use a different country dataset, set `NEMOTRON_PERSONAS_DATASET` in `.env`:

```bash
# .env
NEMOTRON_PERSONAS_DATASET=nvidia/Nemotron-Personas-USA
```

The value must be a valid `nvidia/Nemotron-Personas-*` HuggingFace path. For adding style templates for other countries, see [Backend README](backend/README.md#nemotron-personas).

## 🇸🇬 WOG? Read on.

For Whole-of-Government (WOG) deployments there are two optional add-ons — both independent, pick what you need:

**1. WOG providers** — enable [AIBots](https://aibots.gov.sg) and other WOG-internal connectors:
```bash
# .env
KALEIDOSCOPE_EXTENSIONS=aibots
```
You then select "aibots" during Target Application set-up. Full connector reference: [`backend/src/extensions/aibots/README.md`](backend/src/extensions/aibots/README.md)

**2. Singapore personas** — keep `NEMOTRON_PERSONAS_DATASET` at its default (`nvidia/Nemotron-Personas-Singapore`). Recommended if you need general-purpose personas for a Singapore-context evaluation.

**3. Singapore-contextualised generation prompts** — the built-in LLM prompt templates (`backend/src/common/prompts/templates/`) are written for Singapore government and public-facing digital services (references to CPF, HDB, NS, `.gov.sg`, etc.). They work out of the box for WOG use cases.

To adapt for a different domain, edit the Markdown files in that directory. You can also customise the evaluation/judge prompts (`accuracy_judge.md`, `checkworthy.md`, `*_rubric_judge.md`) to fit your use case.

Reach out to the **AI Practice** team for setup details.

Happy evaluating!

## 📄 License

MIT