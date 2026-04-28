# AIBots Connector

Connects Kaleidoscope to [AIBots](https://aibots.gov.sg) — GovTech's managed LLM platform. Access requires government credentials.

## Enable

```bash
# .env
KALEIDOSCOPE_EXTENSIONS=aibots
```

## Create a Target

```json
{
  "endpoint_type": "aibots",
  "api_endpoint": "https://<aibots-host>/v1.0/api",
  "endpoint_config": {
    "api_key": "<your-X-ATLAS-Key>"
  }
}
```

## `endpoint_config` Reference

| Key | Required | Description |
|-----|----------|-------------|
| `api_key` | ✓ | `X-ATLAS-Key` for authentication |
| `agents` | | List of bot agent UUIDs (default: `[]`) |
| `model` | | LLM identifier, e.g. `azure~openai.gpt-5-mini` |
| `params` | | Model params dict, e.g. `{"temperature": 0.0}` |
| `chat_timeout` | | Timeout (s) for chat creation (default: `30`) |
| `message_timeout` | | Timeout (s) for message send (default: `60`) |

## How It Works

AIBots uses a two-step flow:

1. `POST /chats` with `X-ATLAS-Key` header → returns `chat_id`
2. `POST /chats/{chat_id}/messages` with the prompt → returns response

The connector extracts: answer content, model, tokens, chat ID, message ID, system prompt, guardrails status, and RAG citations.

Reach out to the **AI Practice** team for API credentials and endpoint details.
