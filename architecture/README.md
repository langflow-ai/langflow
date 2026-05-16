# Langflow Architecture Documentation

This folder contains a step-by-step architectural walkthrough of Langflow with Mermaid diagrams.

Langflow is an **open-source visual workflow builder for AI agents**. Think of it as "Figma for LLM pipelines": you drag components (LLMs, prompts, tools, vector stores, agents) onto a canvas, wire them together, and the backend compiles that graph into an executable Python flow. Every flow also becomes an **API endpoint** and can be exposed as an **MCP server tool**.

## Table of Contents

1. [System Context](./01-system-context.md) — who talks to what
2. [Monorepo Layout](./02-monorepo-layout.md) — the four packages
3. [Backend](./03-backend.md) — FastAPI app, routers, services
4. [Graph Engine (LFX)](./04-graph-engine.md) — how flows execute
5. [Frontend](./05-frontend.md) — React + Zustand + xyflow
6. [Request Lifecycle](./06-request-lifecycle.md) — end-to-end flow run
7. [Data Model](./07-data-model.md) — core tables
8. [Deployment](./08-deployment.md) — build & ship
9. [Summary](./09-summary.md) — mental model and reading order

## Quick mental model

A **Flow** is a row in the DB whose `data` column is a JSON graph; the engine hydrates that JSON into a `Graph` of `Vertex` objects, each wrapping a `Component` instance; execution is a topological walk emitting SSE events that the React canvas re-renders live.

## Reading order to learn the codebase fastest

1. `src/lfx/src/lfx/graph/graph/base.py` — the core
2. `src/backend/base/langflow/api/v1/chat.py` — how HTTP meets the core
3. `src/backend/base/langflow/services/deps.py` — how everything is wired
4. `src/frontend/src/stores/flowStore.ts` — how the UI mirrors the graph
