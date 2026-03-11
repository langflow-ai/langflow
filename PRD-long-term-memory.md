# PRD: Long-Term Memory

## 1. Overview

Long-Term Memory gives Langflow flows persistent, searchable recall across conversations. It automatically captures chat messages, optionally preprocesses them through a configurable LLM, and vectorizes them into a per-memory Knowledge Base (Chroma). Builders can create multiple independent memories on the same flow — each with its own embedding model, batch strategy, and LLM preprocessing instructions — then retrieve relevant context via semantic search using a dedicated flow component. This unlocks stateful agents, personalized assistants, and advanced multi-pipeline classification workflows without writing code.

## 2. User Pain Points

- **Flows are stateless by default.** Every execution starts with zero context. A support bot can't recall that the same customer reported the same bug last week — the builder must wire up a custom RAG pipeline over the message history to get any cross-session recall.

- **Building memory manually is high-friction.** To get long-term recall today, a builder must: export messages, chunk them, pick an embedding model, configure a vector store, build a retrieval component, and wire deduplication. Each step is a separate integration to maintain.

- **Raw message vectorization produces noisy recall.** Messages like "ok", "thanks", "hello" become chunks that pollute similarity search results. Competitors like Mem0 and Letta address this with automatic summarization/compaction, but their pipelines are fixed — the builder can't control *what* gets extracted or *how* it's summarized.

- **One memory pipeline per flow is limiting.** Use cases like sentiment tracking, intent classification, and fact extraction each need different LLM instructions over the same message stream. No visual builder today supports multiple independent memory pipelines running in parallel on the same conversation.

## 3. Competitive Landscape

### Mem0

- Managed memory layer that plugs into any agent framework via a single-line SDK call. Handles extraction, consolidation, and retrieval automatically.
- Hybrid storage (vector + graph + key-value) with automatic deduplication, versioning, and TTL support.
- Fixed extraction pipeline — the builder can't customize what gets extracted or how messages are preprocessed. One memory per agent, one pipeline.
- [mem0.ai](https://mem0.ai/) · [Docs](https://docs.mem0.ai/introduction)

### Letta (MemGPT)

- Stateful agent framework where the agent manages its own memory via tool calls. Hierarchical memory: core (always in-context), archival (vector-searchable), recall (conversation history).
- Automatic conversation compaction: when context approaches capacity, the system summarizes history into memory blocks. The agent can read, write, and edit its own memory.
- Powerful but developer-only (Python SDK). No visual builder. Memory structure is predetermined — the builder can't run multiple extraction pipelines with different instructions.
- [letta.com](https://www.letta.com/) · [GitHub](https://github.com/letta-ai/letta)

### Dify

- Visual AI app platform with built-in knowledge bases and conversation variables.
- Short-term memory via TokenBufferMemory (configurable window). Long-term memory requires manually wiring a Knowledge Base — there's no automatic conversation-to-KB pipeline.
- Community-built workarounds exist (e.g., [dify-tool-LongTermMemory](https://github.com/rainchen/dify-tool-LongTermMemory)) but they're not first-party. An open [feature request](https://github.com/langgenius/dify/issues/4149) for "summarize text and store in a vector database" has been open since 2024.
- [dify.ai](https://dify.ai/) · [Docs](https://docs.dify.ai/)

### Flowise

- Visual LLM builder with LangChain-based memory nodes (Buffer, Window, Summary, Zep, Redis).
- Memory is per-session — it buffers recent messages or summarizes them, but doesn't vectorize conversation history into a persistent, searchable knowledge base.
- No automatic capture-to-vector-store pipeline. Long-term recall requires the builder to manually configure external vector stores and retrieval chains.
- [flowiseai.com](https://flowiseai.com/) · [Memory Docs](https://docs.flowiseai.com/integrations/langchain/memory)

### Takeaway

Mem0 and Letta prove that automatic memory extraction with summarization is table stakes for production agents. But both lock the builder into a fixed pipeline. Dify and Flowise don't offer automatic conversation-to-KB pipelines at all. Langflow's opportunity is combining the ease of Mem0's automatic capture with the flexibility of user-defined preprocessing instructions — plus the unique ability to run multiple independent memory pipelines per flow.

## 4. User Journeys

- **No-code builder:** Manually copies chat logs into knowledge bases for recall → Enables auto-capture with one toggle, gets searchable memory instantly → Agents remember users across sessions without custom wiring.

- **Intermediate builder:** Wants recall but embedding costs are high for chatty flows → Configures batch_size=10 with LLM preprocessing to summarize before vectorizing → 10x fewer embedding calls, denser chunks, better retrieval quality.

- **Advanced builder:** Needs sentiment tracking + fact extraction + intent classification from the same conversation → Creates 3 memories with different preprocessing prompts, retrieves each in different branches of the flow → Multi-pipeline memory classification without code.

- **Support team lead:** Wants to retroactively add past conversations to memory → Selects messages in the Messages panel, clicks "Add to Memory" → Historical conversations become searchable context for the agent.

## 5. Requirements

### Functional Requirements

**Memory CRUD**

- A builder must be able to create multiple memories per flow, each with an independent name, embedding model, and configuration.
- A builder must be able to delete a memory, which removes both the database record and the associated KB directory.
- A builder must be able to toggle auto-capture (is_active) on/off per memory without deleting and recreating it.

**Auto-Capture**

- When auto-capture is enabled, new messages persisted to a flow must automatically trigger vectorization into the memory's KB. This must be fire-and-forget (never block message creation).
- Batch size must be configurable (minimum 1). When batch_size > 1, the system must buffer messages and only trigger vectorization when the threshold is reached per session.
- Messages must never be vectorized twice into the same memory (deduplication via MemoryProcessedMessage tracking).

**LLM Preprocessing**

- A builder must be able to enable LLM preprocessing per memory, selecting a model and providing custom instructions.
- Preprocessing must group messages by session before sending to the LLM to prevent cross-session context mixing.
- If the LLM returns "SKIP", the batch must be discarded (not vectorized). If the LLM fails or returns empty, the system must fall back to raw message vectorization.

**Manual Operations**

- A builder must be able to trigger a manual update (vectorize only new/unprocessed messages) from the memory detail screen.
- A builder must be able to trigger a full regeneration (re-vectorize all messages) from the memory detail screen.
- A builder must be able to select specific messages from the Messages panel and add them to a chosen memory.

**Retrieval**

- A flow component must exist that retrieves relevant chunks from a selected memory via semantic similarity search, with configurable top_k.
- The component must return results as a DataFrame usable by downstream flow nodes.

**Status & Observability**

- Memory status must reflect current state: idle, generating, updating, or failed.
- When processing, the UI must poll for updates and show progress indication.
- On failure, the error message must be stored and displayed to the builder.
- Summary metrics must be visible: messages processed, total chunks, sessions captured, pending messages, last generated timestamp.

**Knowledge Base Browsing**

- The builder must be able to browse vectorized chunks in a table, grouped by session.
- The builder must be able to search chunks by content and filter by session.

### Scope

**Included:**
- Memory creation, configuration, deletion
- Auto-capture with batching
- LLM preprocessing with custom instructions
- Manual update, regeneration, and message-add workflows
- Memory retrieval flow component
- Status tracking and error display
- KB document browsing with search and session filter

**Not included:**
- Selective chunk deletion (forget a specific fact)
- Memory TTL / expiration
- Per-end-user memory scoping (memories are per-flow, not per-end-user)
- Graph-based memory relationships (Mem0g-style)
- Memory sharing across flows
- Export/import of memory data

### Edge Cases

- If a memory is deleted while a vectorization task is running, the task must be cancelled.
- If a vectorization is already in progress and the builder triggers another, the system must return a conflict error (HTTP 409) rather than starting a parallel task.
- If the embedding provider's API key becomes invalid after memory creation, the system must fail gracefully, set status to "failed", and show the error — not silently drop messages.
- If the KB directory is deleted externally (e.g., manual filesystem cleanup), the UI should detect the mismatch (total_chunks > 0 but no documents returned) and suggest regeneration.
- If batch_size is changed on an existing memory with pending messages, pending count should be re-evaluated against the new threshold on the next auto-capture trigger.

## 6. Success Metrics

- **Adoption** — percentage of active flows that have at least one memory created — target: 20% within 8 weeks of launch.

- **Auto-capture usage** — percentage of created memories with auto-capture enabled — target: >70% (indicates the feature is useful enough to leave running).

- **Preprocessing adoption** — percentage of memories with LLM preprocessing enabled — target: >25% (indicates builders value the advanced pipeline over raw vectorization).

- **Multi-memory usage** — percentage of memory-using flows with 2+ memories — target: >15% (validates the multi-pipeline differentiation).

## 7. Future Scope (Not MVP)

- **Per-end-user memory scoping** — scope memories to individual end-users rather than the whole flow. Deferred because it requires a user identity system that doesn't exist yet.

- **Selective forget** — delete specific chunks or facts from a memory. Deferred because it requires chunk-level CRUD in the UI and careful handling of the processed-message tracking table.

- **Memory TTL / expiration** — automatically expire chunks after a configurable duration. Deferred because it adds background job complexity and the core use case doesn't require it yet.

- **Graph memory** — store relationships between entities across conversations (like Mem0g). Deferred because it requires a graph database dependency and the vector-based approach covers the initial use cases.

- **Cross-flow memory sharing** — allow multiple flows to read/write the same memory. Deferred because it introduces concurrency and permission challenges.

- **Relevance feedback loop** — track which retrieved chunks were actually useful and use that signal to improve retrieval. Deferred because it requires integration with evaluation/feedback systems.

- **Memory analytics dashboard** — visualize memory growth, retrieval hit rates, and preprocessing quality over time.

## 8. Open Questions

1. **Should memories be scoped per end-user by default?** Currently memories are per-flow — all end-users share the same memory. For support/sales use cases, per-user scoping is essential. Should we add an optional `end_user_id` scope, or is that a v2 concern?

2. **What happens when the vector store grows very large?** Chroma is embedded and file-based. At what scale (chunk count, directory size) do we need to offer an external vector store option (Pinecone, Weaviate, pgvector)?

3. **Should preprocessing prompt templates be shareable?** Builders creating "sentiment tracker" or "fact extractor" memories are likely to converge on similar prompts. Should we offer a template library?

4. **How should memory interact with flow versioning?** If a builder changes the preprocessing prompt, should existing chunks be re-processed, or only new messages use the new prompt? Currently it's the latter — is that sufficient?

5. **Should auto-capture filter by sender type?** Currently all messages (user + AI) are captured. Some builders may only want to capture user messages to avoid vectorizing the AI's own responses. Should sender filtering be a configuration option?
