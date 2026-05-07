---
sidebar_position: 2
title: Installation
---

# Installation

## Prerequisites

- **Docker Desktop** installed and running
- **Git** installed

## Clone and start

```bash
git clone https://github.com/govtech-responsibleai/kaleidoscope.git
cd kaleidoscope
cp .env.example .env
docker compose up -d
```

Wait for all containers to start. You can check status with:

```bash
docker compose ps
```

Once all services are healthy, open [http://localhost:3000](http://localhost:3000) in your browser. Sign in with `dev` / `dev` and start evaluating.

:::info Self-hosting?
If you're deploying Kaleidoscope for your team with shared secrets, review and edit the [provider catalog](https://github.com/govtech-responsibleai/kaleidoscope/blob/main/backend/src/common/llm/provider_catalog.yaml) and `.env` file prior to deployment. See [LLM Providers](../configuration/1_providers.md) for the full reference.
:::
