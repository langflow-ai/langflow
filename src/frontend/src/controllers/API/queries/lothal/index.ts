import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { LothalPhaseId } from "@/pages/lothal/components/phases";
import { api } from "../../api";

// Types use plain names within the `lothal` namespace and mirror the
// `/api/v1/lothal/` contract (api-endpoints.md) exactly. Phase ids are
// declared once — in pages/lothal/components/phases.ts — and re-exported
// here under the contract's name (a type-only import, erased at build).

export type Phase = LothalPhaseId;

export type Project = {
  id: string;
  user_id: string;
  name: string;
  phase: Phase;
  prd_content: string | null;
  // The canonical xyflow graph ({nodes, edges} incl. positions) parsed from the
  // stored JSON string; null until DIAGRAM_GENERATION produces one.
  diagram_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type Message = {
  id: string;
  project_id: string;
  role: "USER" | "ASSISTANT";
  content: string;
  suggestions: string[];
  phase: string;
  created_at: string;
};

// --- Diagram (D2 source + server-rendered SVG, Epic D) ----------------------
// The diagram artifact is D2 source text now, not an xyflow graph (Epic D). The
// generator emits D2 (D.2), the backend persists it verbatim and renders it to
// SVG on read (D.3/D.6); `GET /diagram` hands back both. `d2` is `null` once a
// project is past CLARIFICATION but before the generator has emitted anything;
// `svg` is `null` when there is no `d2` or rendering failed. The frontend just
// displays the SVG and ships no D2 compiler of its own.

export type Diagram = {
  d2: string | null;
  svg: string | null;
};

// --- Legacy xyflow render layer (Story 2.x / B.4) --------------------------
// The pre-D2 graph shape. Still consumed by the decorative <DiagramCanvas> on
// the Landing / Design-System pages (seeded literals, not the live endpoint).
// Removed wholesale once the xyflow canvas path is deleted (Epic D.15).

export type NodeKind = "person" | "service" | "ui" | "data";
export type EdgeKind = "sync" | "async" | "return";

export type DiagramNode = {
  id: string;
  type: "actorNode" | "systemNode";
  data: { label: string; kind?: NodeKind; note?: string };
  position: { x: number; y: number };
};

export type DiagramEdge = {
  id: string;
  source: string;
  target: string;
  animated?: boolean;
  data: { order: number; label?: string; kind?: EdgeKind };
};

export type DiagramGraph = {
  nodes: DiagramNode[];
  edges: DiagramEdge[];
};

// A single generated file. Mirrors `CodeFile` / `CodeResponse` in the contract
// (`langflow/lothal/schemas.py`): `GET /code` returns `{ files: CodeFile[] }`.
export type CodeFile = {
  path: string;
  content: string;
};

const BASE = "/api/v1/lothal/projects/";

const PROJECTS_KEY = ["lothal", "projects"] as const;
// Single-project keys extend PROJECTS_KEY, so list-level invalidations
// (create/delete/chat) cascade to every open single-project query too.
const projectKey = (projectId: string) => [...PROJECTS_KEY, projectId] as const;
const messagesKey = (projectId: string) =>
  ["lothal", "messages", projectId] as const;
const diagramKey = (projectId: string) =>
  ["lothal", "diagram", projectId] as const;
const codeKey = (projectId: string) => ["lothal", "code", projectId] as const;

// Deterministic failures must not be retried — retrying only delays the state
// the UI keys off them: a structured 501 (contract stub), a 403 (phase gate),
// a 404 (missing or foreign project). Real transient failures (network, 5xx)
// still get a couple of attempts.
const retrySkipping =
  (...statuses: number[]) =>
  (count: number, error: unknown): boolean => {
    const status = (error as { response?: { status?: number } })?.response
      ?.status;
    return (status === undefined || !statuses.includes(status)) && count < 2;
  };

const skip501Retry = retrySkipping(501);

// The stub-backed queries (messages/diagram/code) have nothing fresher to
// fetch for minutes at a time — and react-query's default staleTime of 0
// refetches them on every window focus, hammering known-501 endpoints. Once
// live they stay correct: every mutation that changes them invalidates their
// keys, which bypasses staleTime.
const STUB_STALE_MS = 5 * 60 * 1000;

// --- Projects --------------------------------------------------------------

async function listProjects(): Promise<Project[]> {
  const res = await api.get<Project[]>(BASE);
  return res.data;
}

async function createProject(name: string): Promise<Project> {
  const res = await api.post<Project>(BASE, { name });
  return res.data;
}

async function deleteProject(id: string): Promise<void> {
  await api.delete(`${BASE}${id}`);
}

export function useProjects() {
  return useQuery({ queryKey: PROJECTS_KEY, queryFn: listProjects });
}

export function useProject(id: string) {
  return useQuery({
    queryKey: projectKey(id),
    queryFn: async () => {
      const res = await api.get<Project>(`${BASE}${id}`);
      return res.data;
    },
    enabled: id.length > 0,
    // A 404 is deterministic — the project is gone, or another user's.
    retry: retrySkipping(404),
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createProject,
    onSuccess: () => qc.invalidateQueries({ queryKey: PROJECTS_KEY }),
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteProject,
    onSuccess: () => qc.invalidateQueries({ queryKey: PROJECTS_KEY }),
  });
}

// --- Messages --------------------------------------------------------------

export function useMessages(projectId: string) {
  return useQuery({
    queryKey: messagesKey(projectId),
    queryFn: async () => {
      const res = await api.get<Message[]>(`${BASE}${projectId}/messages`);
      return res.data;
    },
    // The endpoint is a 501 stub until Epic 1 — don't retry that (the UI keys
    // its NotReady state off the error, and retrying just delays it).
    retry: skip501Retry,
    staleTime: STUB_STALE_MS,
  });
}

export function useSendMessage(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (content: string) => {
      const res = await api.post<Message>(`${BASE}${projectId}/chat`, {
        content,
      });
      return res.data;
    },
    onSuccess: () => {
      // The reply may advance the phase or (re)generate the diagram — refresh the
      // conversation, the project list (phase badge), and the diagram (canvas).
      qc.invalidateQueries({ queryKey: messagesKey(projectId) });
      qc.invalidateQueries({ queryKey: PROJECTS_KEY });
      qc.invalidateQueries({ queryKey: diagramKey(projectId) });
    },
  });
}

// --- Diagram ---------------------------------------------------------------

export function useDiagram(projectId: string, enabled = true) {
  return useQuery({
    queryKey: diagramKey(projectId),
    queryFn: async () => {
      const res = await api.get<Diagram>(`${BASE}${projectId}/diagram`);
      return res.data;
    },
    // Phase-gated: the canvas only enables this past CLARIFICATION (no diagram
    // exists before then). The 501 stub (until Epic 2) and the 403 phase gate
    // are both deterministic — the UI keys NotReady off them.
    enabled,
    retry: retrySkipping(501, 403),
    staleTime: STUB_STALE_MS,
  });
}

// --- Code ------------------------------------------------------------------

// The generated files for a project. A 501 stub until Epic 4 lights up code
// generation; the Code view keys its NotReady state off that. `files` is `[]`
// while generation is in progress.
export function useCode(projectId: string) {
  return useQuery({
    queryKey: codeKey(projectId),
    queryFn: async () => {
      const res = await api.get<{ files: CodeFile[] }>(
        `${BASE}${projectId}/code`,
      );
      return res.data.files;
    },
    retry: skip501Retry,
    staleTime: STUB_STALE_MS,
  });
}
