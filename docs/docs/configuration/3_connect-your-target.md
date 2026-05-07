---
sidebar_position: 3
title: Connect Your Target
---

# Connecting Your AI Application

A **target** is the AI application you want to evaluate. It can be a chatbot, a RAG system, a customer service agent, or any service that takes an input and produces an outcome.

## Target Details

When you create a target, you provide:

| Field | Required | Description |
|-------|----------|-------------|
| **Name** | Yes | A label for this target, such as the application or bot name |
| **Agency** | No | The team or organisation that owns it |
| **Purpose** | No | What the application is meant to help users do |
| **Target users** | No | Who the application serves |

These details help Kaleidoscope generate more relevant personas and test inputs for your evaluation.

## Configuring the Endpoint

Kaleidoscope calls your target's API during evaluation. You need to provide:

1. **API Endpoint** - the URL Kaleidoscope sends inputs to (e.g. `https://my-bot.example.com/chat`)
2. **Connector Type** - how to communicate with the endpoint. The built-in **HTTP** connector works for most REST APIs.
3. **Body Template** - the JSON request body. Use `{{prompt}}` as a placeholder for where the input should go (defaults to `{"prompt": "{{prompt}}"}`).

### Authentication

If your endpoint requires an API key, Kaleidoscope supports three presets:

- **Bearer** - sends `Authorization: Bearer <secret>`
- **x-api-key** - sends `x-api-key: <secret>`
- **api-key** - sends `api-key: <secret>`

Secrets are encrypted at rest and masked in the UI after saving.

## Testing Your Connection

Start by clicking **Probe Endpoint** to send a test input and inspect the raw response from your target - status code, headers, and full JSON body. This helps you understand the shape of the response so you can define your extraction paths.

Once you can see your target's response structure, you need to tell Kaleidoscope where to find the outputs using dot-notation paths:

- **Response Content Path** - where to find the actual output text. For example, if your target returns `{"choices": [{"message": {"content": "Hello!"}}]}`, the path would be `choices.0.message.content`.
- **Retrieved Context Path** - (optional) where to find retrieved documents, if your target is a RAG system. This grounding context is used during claim-based accuracy scoring to verify whether the target's claims are supported by its sources.

Once your response paths are configured, use **Test Connection** to verify the full pipeline end-to-end. This sends a sample input, extracts the output using your configured paths, and confirms everything works.

## Knowledge Base

Optionally upload documents (PDF, DOCX, TXT, or Markdown) that describe what your application should know. Kaleidoscope uses these to:

- Generate in-scope and out-of-scope test inputs
- Evaluate accuracy claims against source material
- Provide context to judges during claim-based scoring

## What's Next

Before creating a target, make sure you have configured at least one [LLM Provider](./1_providers.md). Kaleidoscope uses provider models to generate evaluation inputs, run judges, and create the default rubrics and judges for a new target.

:::info For developers
Kaleidoscope supports custom connectors via an extension system. Set the `KALEIDOSCOPE_EXTENSIONS` environment variable (comma-separated) to load additional connector types at startup. Each extension registers itself with the connector registry and appears as an option in the UI. See the built-in `aibots` extension for a reference implementation.
:::
