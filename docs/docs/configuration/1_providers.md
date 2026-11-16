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
| **Gemini** | `GEMINI_API_KEY` | `gemini/gemini-3.1-flash-lite` |
| **OpenAI** | `OPENAI_API_KEY` | `openai/gpt-5.4-nano` |
| **Azure OpenAI** | `AZURE_API_KEY`, `AZURE_API_BASE` | `azure/gpt-5.4-nano` |
| **Anthropic** | `ANTHROPIC_API_KEY` | `anthropic/claude-haiku-4-5` |
| **AWS Bedrock** | `AWS_BEARER_TOKEN_BEDROCK` | `bedrock/anthropic.claude-haiku-4-5-20251001-v1:0` |
| **OpenRouter** | `OPENROUTER_API_KEY` (optional: `OPENROUTER_API_BASE`) | `openrouter/openrouter/free` |
| **Fireworks** | `FIREWORKS_AI_API_KEY` | `fireworks/qwen3p6-plus` |
| **GovTech AI Platform** | `PLATFORM_API_KEY`, `PLATFORM_API_BASE_URL` | `govtech/gpt-5.6-luna` |

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

The provider's `default_model` appears first in dropdowns and registered-model lists once credentials are configured. Additional models listed under `common_models` appear after the default model, with duplicates removed.

### OpenAI-compatible gateways

Some providers, such as the GovTech AI Platform, expose many upstream models behind one OpenAI-compatible endpoint. Declare `litellm_route` to tell Kaleidoscope which LiteLLM provider to call on the wire while keeping the provider's own prefix in the UI and database:

```yaml
  - key: govtech
    display_name: GovTech AI Platform
    litellm_prefix: govtech/
    litellm_route: openai/
    credential_fields:
      - key: PLATFORM_API_KEY
        label: API Key
        env_var: PLATFORM_API_KEY
        required: true
      - key: PLATFORM_API_BASE_URL
        label: API Base
        env_var: PLATFORM_API_BASE_URL
        required: true
    default_model: govtech/gpt-5.6-luna
    pricing:
      govtech/bedrock.claude-haiku-4-5:
        input: 1.00
        output: 5.00
        cache_read: 0.10
```

A model named `govtech/gpt-5.6-luna` is sent to LiteLLM as `openai/gpt-5.6-luna` with the configured `api_base`. Use the model IDs exactly as the platform lists them (for example `bedrock.claude-haiku-4-5` or `gemini-3.5-flash-lite`).

LiteLLM does not know prices for gateway models, so cost tracking reports zero unless you declare `pricing` (USD per 1M tokens: `input`, `output`, optional `cache_read`). Prices are registered at startup under both the routed name and the bare model name when LiteLLM does not know the model. If LiteLLM prices the bare name under a different provider (for example a Gemini model called through the gateway), only the routed name is registered. If LiteLLM already prices the bare name under the same provider as the route, the catalog entry is ignored with a warning and LiteLLM's own price is used, because LiteLLM would merge the routed name into its existing entry.

## Managing Credentials in the UI

Navigate to **Providers** in the sidebar to see all providers and their status:

- **Configured** (green) - all required fields are filled; models from this provider are available
- **Managed** (blue) - shared credentials set by the administrator (read-only for users)
- **Not set** (grey) - no credentials configured; models from this provider won't appear in dropdowns
