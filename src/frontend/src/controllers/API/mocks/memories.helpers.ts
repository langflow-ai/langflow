import type {
  MemoryDocumentItem,
  MemoryInfo,
  MemoryStatus,
  MockDb,
} from "../queries/memories/types";

const STORAGE_KEY = "langflow.mock.memories.v1";

export const nowIso = () => new Date().toISOString();

export const randomId = (prefix: string) =>
  `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 9)}`;

const safeLoad = (): MockDb => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { memories: {}, documents: {} };
    const parsed = JSON.parse(raw) as MockDb;
    return {
      memories: parsed.memories ?? {},
      documents: parsed.documents ?? {},
    };
  } catch {
    return { memories: {}, documents: {} };
  }
};

const safeSave = (db: MockDb) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(db));
  } catch {
    // ignore
  }
};

export const getDb = (): MockDb => safeLoad();

export const setDb = (db: MockDb) => safeSave(db);

export const computeSessions = (docs: MemoryDocumentItem[]) => {
  const set = new Set<string>();
  for (const d of docs) set.add(d.session_id || "");
  return Array.from(set).filter(Boolean).sort();
};

export const applySearch = (docs: MemoryDocumentItem[], search?: string) => {
  const q = (search ?? "").trim().toLowerCase();
  if (!q) return docs;
  return docs.filter((d) => (d.content ?? "").toLowerCase().includes(q));
};

export const normalizeBatchSize = (n: unknown) => {
  const parsed = typeof n === "number" ? n : parseInt(String(n ?? ""), 10);
  const intVal = Number.isFinite(parsed) ? Math.trunc(parsed) : NaN;
  return Number.isFinite(intVal) && intVal >= 1 ? intVal : 1;
};

export const setStatusAsync = (
  memoryId: string,
  status: MemoryStatus,
  delayMs: number,
) => {
  window.setTimeout(() => {
    const db = getDb();
    const mem = db.memories[memoryId];
    if (!mem) return;
    // If user deleted the memory or started another run, do nothing.
    if (mem.status !== status) return;

    const next: MemoryInfo = {
      ...mem,
      status: "idle",
      error_message: undefined,
      updated_at: nowIso(),
      last_generated_at:
        status === "generating" ? nowIso() : mem.last_generated_at,
    };

    db.memories[memoryId] = next;
    setDb(db);
  }, delayMs);
};
