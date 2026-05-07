---
sidebar_position: 1
title: LLM Providers
---

# LLM Providers

Kaleidoscope uses LLM models for input generation, persona creation, and judge scoring. You need at least one provider configured to run evaluations.

## Credential Sources

Credentials can come from two places:

| Source | Set by | Scope | How |
|--------|--------|-------|-----|
| **Shared** | Administrator | All users | `.env` file or system environment variables |
| **Personal** | Each user | That user only | Providers page in the UI (encrypted in database) |

If a shared key is already configured for a provider, users see it as "Managed" and cannot override it with personal credentials.

## Supported Providers

| Provider | Environment Variable(s) | Default Model |
|----------|------------------------|---------------|
| **Gemini** | `GEMINI_API_KEY` | `gemini/gemini-3.1-flash-lite-preview` |
| **OpenAI** | `OPENAI_API_KEY` | `openai/gpt-5.4-nano` |
| **Azure OpenAI** | `AZURE_API_KEY`, `AZURE_API_BASE` | `azure/gpt-5.4-nano` |
| **Anthropic** | `ANTHROPIC_API_KEY` | `anthropic/claude-haiku-4-5` |
| **AWS Bedrock** | `AWS_BEARER_TOKEN_BEDROCK` | `bedrock/anthropic.claude-haiku-4-5-20251001-v1:0` |
| **OpenRouter** | `OPENROUTER_API_KEY` (optional: `OPENROUTER_API_BASE`) | `openrouter/openrouter/free` |
| **Fireworks** | `FIREWORKS_AI_API_KEY` | `fireworks/qwen3p6-plus` |

:::note
Default models are intentionally small. We recommend running multiple small models as judges and calculating their reliability scores as a baseline. After which, you can add more advanced models and compare whether the cost increase is justified by improved alignment.
:::

## Services

| Service | Environment Variable | Purpose |
|---------|---------------------|---------|
| **Serper** | `SERPER_API_KEY` | Web search for grounding input generation in real-world context |

## Managing the Provider Catalog

The provider catalog lives at [`backend/src/common/llm/provider_catalog.yaml`](https://github.com/govtech-responsibleai/kaleidoscope/blob/main/backend/src/common/llm/provider_catalog.yaml). Edit this file if you need to:

- Configure shared secrets for your deployment
- Add new models to an existing provider
- Add an entirely new provider

Each provider entry follows this structure:

```yaml
providers:
  - key: openai
    display_name: OpenAI
    litellm_prefix: openai/
    logo_path: /icons/OpenAI-black-monoblossom.png
    credential_fields:
      - key: OPENAI_API_KEY
        label: API Key
        env_var: OPENAI_API_KEY
        required: true
    default_model: openai/gpt-5.4-nano
    common_models:
      - openai/gpt-5.4
      - openai/gpt-5.4-mini
    embedding_models:
      - openai/text-embedding-3-small
```

Models listed under `common_models` appear in dropdowns throughout the UI once the provider's credentials are configured.

## Managing Credentials in the UI

Navigate to **Providers** in the sidebar to see all providers and their status:

- **Configured** (green) - all required fields are filled; models from this provider are available
- **Managed** (blue) - shared credentials set by the administrator (read-only for users)
- **Not set** (grey) - no credentials configured; models from this provider won't appear in dropdowns