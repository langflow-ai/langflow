import type {
  CreateMemoryPayload,
  MemoryDocumentItem,
  MemoryDocumentsResponse,
  MemoryInfo,
  UpdateMemoryPayload,
} from "../queries/memories/types";
import {
  applySearch,
  computeSessions,
  getDb,
  normalizeBatchSize,
  nowIso,
  randomId,
  setDb,
  setStatusAsync,
} from "./memories.helpers";

export const mockMemoriesApi = {
  reset() {
    setDb({ memories: {}, documents: {} });
  },

  async list(flowId?: string): Promise<MemoryInfo[]> {
    const db = getDb();
    const all = Object.values(db.memories);
    const filtered = flowId ? all.filter((m) => m.flow_id === flowId) : all;
    // newest first
    return filtered.sort(
      (a, b) =>
        new Date(b.created_at ?? 0).getTime() -
        new Date(a.created_at ?? 0).getTime(),
    );
  },

  async get(memoryId: string): Promise<MemoryInfo> {
    const db = getDb();
    const mem = db.memories[memoryId];
    if (!mem) {
      const err = new Error("Memory not found");
      (err as any).status = 404;
      throw err;
    }
    const docs = db.documents[memoryId] ?? [];
    return {
      ...mem,
      documents: docs,
      documents_total: docs.length,
      document_sessions: computeSessions(docs),
    };
  },

  async create(payload: CreateMemoryPayload): Promise<MemoryInfo> {
    const db = getDb();
    const id = randomId("mem");
    const created_at = nowIso();
    const name = payload.name?.trim() || "Untitled Memory";
    const batch_size = normalizeBatchSize(payload.batch_size);

    const mem: MemoryInfo = {
      id,
      name,
      description: payload.description,
      kb_name: `kb_${name.replace(/\s+/g, "_").toLowerCase()}_${id.slice(-6)}`,
      embedding_model: payload.embedding_model,
      embedding_provider: payload.embedding_provider,
      is_active: payload.is_active ?? true,
      status: "idle",
      error_message: undefined,
      total_messages_processed: 0,
      total_chunks: 0,
      sessions_count: 0,
      batch_size,
      preprocessing_enabled: Boolean(payload.preprocessing_enabled),
      preprocessing_model: payload.preprocessing_model,
      preprocessing_prompt: payload.preprocessing_prompt,
      pending_messages_count: 0,
      user_id: "mock-user",
      flow_id: payload.flow_id,
      created_at,
      updated_at: created_at,
      last_generated_at: undefined,
      documents: [],
      documents_total: 0,
      document_sessions: [],
    };

    const seededDocs: MemoryDocumentItem[] = [
      {
        message_id: randomId("msg"),
        session_id: randomId("sess"),
        sender: "system",
        content: `Seeded memory: ${name}`,
        timestamp: created_at,
      },
    ];

    db.memories[id] = mem;
    db.documents[id] = seededDocs;
    setDb(db);
    return mem;
  },

  async update(
    memoryId: string,
    patch: UpdateMemoryPayload,
  ): Promise<MemoryInfo> {
    const db = getDb();
    const existing = db.memories[memoryId];
    if (!existing) {
      const err = new Error("Memory not found");
      (err as any).status = 404;
      throw err;
    }

    const next: MemoryInfo = {
      ...existing,
      ...patch,
      batch_size:
        patch.batch_size !== undefined
          ? normalizeBatchSize(patch.batch_size)
          : existing.batch_size,
      updated_at: nowIso(),
    };

    db.memories[memoryId] = next;
    setDb(db);
    return next;
  },

  async remove(memoryId: string): Promise<void> {
    const db = getDb();
    delete db.memories[memoryId];
    delete db.documents[memoryId];
    setDb(db);
  },

  async generate(memoryId: string): Promise<MemoryInfo> {
    const db = getDb();
    const existing = db.memories[memoryId];
    if (!existing) {
      const err = new Error("Memory not found");
      (err as any).status = 404;
      throw err;
    }

    // Simulate background work.
    const next: MemoryInfo = {
      ...existing,
      status: "generating",
      error_message: undefined,
      total_messages_processed: 0,
      total_chunks: 0,
      sessions_count: 0,
      pending_messages_count: 0,
      updated_at: nowIso(),
    };

    db.memories[memoryId] = next;

    // Create a few placeholder docs so the UI has something to render.
    const docs: MemoryDocumentItem[] = Array.from({ length: 5 }).map(
      (_, idx) => ({
        message_id: randomId("msg"),
        session_id: `session_${idx % 2 === 0 ? "a" : "b"}`,
        sender: idx % 2 === 0 ? "Human" : "Machine",
        timestamp: nowIso(),
        content: `Mock chunk ${idx + 1} for memory \"${next.name}\"`,
      }),
    );

    db.documents[memoryId] = docs;

    db.memories[memoryId] = {
      ...next,
      total_messages_processed: 5,
      total_chunks: docs.length,
      sessions_count: computeSessions(docs).length,
      documents: docs,
      documents_total: docs.length,
      document_sessions: computeSessions(docs),
    };

    setDb(db);
    setStatusAsync(memoryId, "generating", 1200);
    return db.memories[memoryId];
  },

  async updateKb(memoryId: string): Promise<MemoryInfo> {
    const db = getDb();
    const existing = db.memories[memoryId];
    if (!existing) {
      const err = new Error("Memory not found");
      (err as any).status = 404;
      throw err;
    }

    const next: MemoryInfo = {
      ...existing,
      status: "updating",
      error_message: undefined,
      updated_at: nowIso(),
    };

    db.memories[memoryId] = next;
    setDb(db);

    setStatusAsync(memoryId, "updating", 900);
    return next;
  },

  async addMessages(
    memoryId: string,
    messageIds: string[],
  ): Promise<MemoryInfo> {
    const db = getDb();
    const existing = db.memories[memoryId];
    if (!existing) {
      const err = new Error("Memory not found");
      (err as any).status = 404;
      throw err;
    }

    const docs = db.documents[memoryId] ?? [];
    const newDocs: MemoryDocumentItem[] = messageIds.map((mid) => ({
      message_id: mid,
      session_id: "manual",
      sender: "Human",
      timestamp: nowIso(),
      content: `Mock vectorized content for message ${mid}`,
    }));

    const merged = [...newDocs, ...docs];

    db.documents[memoryId] = merged;
    db.memories[memoryId] = {
      ...existing,
      status: "idle",
      error_message: undefined,
      total_messages_processed:
        existing.total_messages_processed + messageIds.length,
      total_chunks: merged.length,
      sessions_count: computeSessions(merged).length,
      updated_at: nowIso(),
      documents: merged,
      documents_total: merged.length,
      document_sessions: computeSessions(merged),
    };

    setDb(db);
    return db.memories[memoryId];
  },

  async documents(params: {
    memoryId: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<MemoryDocumentsResponse> {
    const db = getDb();
    const docs = db.documents[params.memoryId] ?? [];
    const filtered = applySearch(docs, params.search);
    const offset = Math.max(0, params.offset ?? 0);
    const limit = Math.max(0, params.limit ?? 100);
    const paged = filtered.slice(offset, offset + limit);

    return {
      documents: paged,
      total: filtered.length,
      sessions: computeSessions(docs),
    };
  },
};

export const isMockMemoriesEnabled = () => {
  // NOTE: Jest in this repo isn't configured for `import.meta`, so we must not
  // reference it directly at parse-time.
  let flag: unknown;
  try {
    flag = Function(
      "return import.meta && import.meta.env && import.meta.env.VITE_MOCK_MEMORIES_API",
    )();
  } catch {
    flag = undefined;
  }
  return true || flag === "true" || flag === true;
};
