# Langflow Unified Roadmap

| Category | Feature | Status | Description |
|----------|---------|--------|-------------|
| Building Experience | **Agent-Centric UX** | In Progress | Agents as first-class entities with integrated tool management, context, and control. The Agent owns context, tools, state, memory, and prompts, with clearer defaults and interactions. |
| | | | - Agent Control Center — dedicated panel with model provider settings, system prompt, tools, memory, outputs, and logs |
| | | | - Model-Agnostic — full compatibility with non-OpenAI models, including tool calling and JSON mode |
| | | | - Integrated Prompt Experience — in-Agent prompt editor with smart variable detection, syntax validation, and presets |
| | | | - Context & State Management — global context variables, Set State node, and persistent execution checkpoints |
| | | | - Direct Tool Attachments — add and manage tools directly inside the Agent component |
| AI-Assisted Features | **Langflow Assistant** | In Progress | A shared LLM layer powering intelligent assistance throughout the Langflow experience. |
| | | | - Flow Generation — AI-assisted flow creation from natural language descriptions |
| | | | - Prompt Help — suggestions, improvements, and validation for prompts |
| | | | - Custom Code Creation — AI-generated component code and transformations |
| Innovation | **Agentic Capabilities** | In Progress | A single, configurable agent component that feels simple but is powered by deep architecture, safety, reasoning, and orchestration patterns. A modular, safe, intelligent operator with toggleable capabilities — equally suitable for hobby projects and enterprise automation. |
| | | | - Human in the Loop — approval gates and interactive decision points |
| | | | - Guardrails — safety constraints and output validation |
| | | | - Tool Hooks — pre/post-execution hooks for tool calls |
| | | | - Reasoning & Planning — step-by-step planning and chain-of-thought capabilities |
| | | | - Skills — composable, reusable agent behaviors |
| | | | - Policies — declarative rules governing agent behavior and boundaries |
| Production Readiness | **API Redesign** | In Progress | Redesign Langflow's API to meet production-grade standards through clear structure, consistent schemas, and modern REST conventions. |
| | | | - Ensure parity between API and LFX structures |
| | | | - Simplify JSON responses |
| | | | - Make API schema definition a natural part of flow building |
| Production Readiness | **Flow Publishing** | In Progress | Enable users to deploy, integrate, or publish Langflow projects through a unified configuration flow. |
| | | | - Deployment Configurations — flexible options for hosting, exposing, and connecting flows to real-world systems |
| | | | - Publish Methods: API/SDK, MCP Server, Embedded Chat |
| Innovation | **Long-Term Memory** | Not Started | Persistent, searchable recall across conversations. Automatically captures chat messages, optionally preprocesses them through a configurable LLM, and vectorizes them into a per-memory Knowledge Base (Chroma). |
| | | | - Multiple independent memories per flow — each with its own embedding model, batch strategy, and LLM preprocessing instructions |
| | | | - Retrieval via semantic search using a dedicated flow component |
| | | | - Enables stateful agents, personalized assistants, and advanced multi-pipeline classification workflows without writing code |
| Core Platform | **Knowledge Bases & Retrieval** | Not Started | Build a unified ingestion and retrieval system to power Agentic RAG in Langflow. |
| Core Platform | **DB Connectors / Providers** | Not Started | Native database connectors — similar to model providers but for a curated list of 3-5 core databases. Enables native ingestion and management so that RAG goes beyond Chroma with local storage. |
| Architecture | **Langflow Bundle Separation** | Not Started | Separate Langflow's 100+ integration components (bundles) from the main repository into independently-owned external repos. |
| | | | - Ship Langflow with a small core set (~15-20 non-vendor components) |
| | | | - Introduce a tiered ownership model for integrations |
| | | | - Add an in-app marketplace for users to discover and install community bundles on demand |
| Extensibility | **MCP Integrations** | Not Started | Strengthen Langflow's Model Context Protocol (MCP) foundation for tool and connector extensibility. |
| | | | - Improve UX for adding and managing custom MCP servers |
| | | | - Provide curated list of popular pre-loaded MCPs (Slack, Notion, etc.) |
| | | | - Include robust and seamless integrations with most popular SaaS connectors |
| Onboarding | **Improved Onboarding** | Not Started | Provide a smooth first-time experience for new users. |
| | | | - Embedded Intro Video — short tutorial automatically shown on first project creation |
| | | | - Guided Provider Setup — walkthrough to add API keys and select model/embedding providers |
| | | | - Starter Flow Templates — modernize and refresh starter templates to align with MCP and Knowledge Base-powered experiences |
| Innovation | **Model Evaluation** | Not Started | Systematically test, compare, and improve AI flows by turning real interactions into reusable benchmarks. |
| | | | - Playground messages are automatically stored in an evals table |
| | | | - Rerun and re-score entire conversations with different flow parameters, models, prompts, or tools |
| Developer Experience | **Documentation Redesign** | Not Started | Redesign the visual and structural layer of docs.langflow.org to reduce time-to-first-success for new developers and improve navigation speed for returning users. |
| | | | - Typography, sidebar navigation, content components, code block styling, and dark mode |
| | | | - No changes to documentation content or URLs |
| Polish & Completion | **Knowledge Bases (improvements)** | Various | Remaining improvements to the KB feature set |
| Polish & Completion | **New Playground** | Various | Complete and polish the redesigned Playground |
| Polish & Completion | **Data Types Unification** | Various | Unify data type handling across the platform |
| Polish & Completion | **API v2 Improvements** | Various | Continued refinements to API v2 |
| Polish & Completion | **UX to Define Schema** | Various | User-facing interface for schema definition |
| Polish & Completion | **Documentation UX Revamp** | Various | Content and structure improvements beyond visual redesign |
| Polish & Completion | **Component Fields Cleanup** | Various | Remove non-functioning fields; add most fields as advanced mode to show in Inspector Panel |
