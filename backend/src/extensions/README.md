# Kaleidoscope Extensions

Extensions add optional connector types to Kaleidoscope. The core library ships with the `http` connector; everything else is an extension.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KALEIDOSCOPE_EXTENSIONS` | `""` | Comma-separated list of extensions to load at startup (e.g. `aibots,custom`) |

Extensions are loaded during app startup (`src/main.py` lifespan). Each extension's `register()` function is called, which registers its connector with the registry and extends the `EndpointType` enum so the API accepts the new type.

## Built-in Connector: HTTP

The `http` connector is always available (no extension needed). It sends a single HTTP request to any REST API endpoint.

### Required `endpoint_config`

| Key | Description |
|-----|-------------|
| `response_content_path` | Dot-notation path to extract the answer text from the JSON response (e.g. `choices.0.message.content`) |

### Optional `endpoint_config`

| Key | Default | Description |
|-----|---------|-------------|
| `method` | `POST` | HTTP method |
| `headers` | `{}` | Dict of request headers (e.g. `{"Authorization": "Bearer <token>"}`) |
| `body_template` | `{"prompt": "<text>"}` | Request body. The string `{{prompt}}` anywhere in a value is replaced with the actual prompt at runtime |
| `timeout` | `60` | Request timeout in seconds |
| `response_model_path` | — | Dot-notation path to extract model name from response |
| `retrieved_context_path` | — | Dot-notation path to extract retrieved grounding context from the response. Kaleidoscope normalizes this value into `answer.rag_citations` for claim-level accuracy scoring |
| `response_tokens_path` | — | Dot-notation path to extract token usage from response |

### Example: OpenAI-compatible endpoint

```json
{
  "endpoint_type": "http",
  "api_endpoint": "https://api.openai.com/v1/chat/completions",
  "endpoint_config": {
    "headers": { "Authorization": "Bearer sk-..." },
    "body_template": {
      "model": "gpt-4",
      "messages": [{ "role": "user", "content": "{{prompt}}" }]
    },
    "response_content_path": "choices.0.message.content",
    "retrieved_context_path": "rag.chunks",
    "response_model_path": "model",
    "response_tokens_path": "usage"
  }
}
```

## Writing a Custom Connector Extension

### 1. Create the extension package

```
src/extensions/<name>/
    __init__.py
    connector.py
```

### 2. Implement the connector

`src/extensions/<name>/connector.py`:

```python
from src.common.connectors.base import TargetConnector, ConnectorResponse

class MyConnector(TargetConnector):
    @classmethod
    def validate_config(cls, config: dict):
        """Validate endpoint_config when a target is created/updated.

        Raise ValueError for missing or invalid fields.
        """
        if not config.get("required_field"):
            raise ValueError("required_field is required in endpoint_config")

    async def send_message(self, prompt: str) -> ConnectorResponse:
        """Send a prompt to the target and return the response.

        self.endpoint_url  - the target's api_endpoint
        self.config        - the target's endpoint_config dict
        """
        # ... call the API ...
        return ConnectorResponse(
            content="the answer text",
            raw_response={},        # full API response for traceability
            model="model-name",     # optional
            tokens={},              # optional token usage dict
            metadata={},            # optional provider-specific data
        )
```

### 3. Register the connector

`src/extensions/<name>/__init__.py`:

```python
def register():
    from src.common.connectors.registry import register_connector
    from src.extensions.<name>.connector import MyConnector
    register_connector("<name>", MyConnector)
```

### 4. Enable the extension

Add the extension name to the `KALEIDOSCOPE_EXTENSIONS` env var:

```bash
# .env or Docker env
KALEIDOSCOPE_EXTENSIONS=<name>
```

On startup, the registry will:
- Add the connector class so `get_connector()` can instantiate it
- Extend the `EndpointType` enum so the API accepts the new type in target create/update requests
- Call `validate_config()` when users create or update targets with this endpoint type

## AIBots Extension (Government Only)

The AIBots extension (`src/extensions/aibots/`) connects to the [AIBots platform](https://aibots.gov.sg), which is restricted to government officers.

### Setup

1. Ensure the `src/extensions/aibots/` directory is present in your deployment
2. Set the environment variable:
   ```bash
   KALEIDOSCOPE_EXTENSIONS=aibots
   ```
3. Create a target with:
   ```json
   {
     "endpoint_type": "aibots",
     "api_endpoint": "https://<aibots-host>/v1/api",
     "endpoint_config": {
       "api_key": "<your X-ATLAS-Key>"
     }
   }
   ```

### Optional `endpoint_config` for AIBots

| Key | Default | Description |
|-----|---------|-------------|
| `agents` | `[]` | List of bot agent UUIDs |
| `model` | — | LLM identifier (e.g. `azure~openai.gpt-5-mini`) |
| `params` | — | Model parameters dict (e.g. `{"temperature": 0.0}`) |
| `chat_timeout` | `30` | Timeout in seconds for chat creation |
| `message_timeout` | `60` | Timeout in seconds for message send |

### How it works

AIBots uses a two-step flow (which is why it can't use the generic HTTP connector):

1. **Create chat session** — `POST /chats` with `X-ATLAS-Key` header
2. **Send message** — `POST /chats/{id}/messages` with the prompt

The connector extracts: answer content, model, tokens, chat ID, message ID, system prompt, guardrails status, and RAG citations from the response.
