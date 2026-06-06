import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";

// Types use plain names within the `lothal` namespace and mirror the
// `/api/v1/lothal/` contract (api-endpoints.md) exactly.

export type Phase =
  | "CLARIFICATION"
  | "DIAGRAM_GENERATION"
  | "DIAGRAM_REFINEMENT"
  | "CODE_GENERATION"
  | "DONE";

export type Project = {
  id: string;
  user_id: string;
  name: string;
  phase: Phase;
  prd_content: string | null;
  diagram_mmd: string | null;
  diagram_layout: Record<string, unknown> | null;
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

// --- Diagram (xyflow render layer) -----------------------------------------
// Mirrors the `GET /diagram` contract. `data.label` is the only guaranteed node
// field; `kind`/`note` are optional render hints the converter may add (not part
// of the LLM contract). Edges always carry `data.order`; `data.kind` is an
// optional render hint (sync/async/return) derived from the Mermaid arrow style.

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
  label: string;
  data: { order: number; kind?: EdgeKind };
};

export type Diagram = {
  mermaid: string | null;
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
const messagesKey = (projectId: string) =>
  ["lothal", "messages", projectId] as const;
const diagramKey = (projectId: string) =>
  ["lothal", "diagram", projectId] as const;
const codeKey = (projectId: string) => ["lothal", "code", projectId] as const;

// A structured 501 (the contract's "not implemented yet" stub) is terminal —
// retrying just delays the NotReady state. Real transient failures still retry.
const skip501Retry = (count: number, error: unknown): boolean => {
  const status = (error as { response?: { status?: number } })?.response
    ?.status;
  return status !== 501 && count < 2;
};

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
      // The reply may advance the phase — refresh both the conversation and
      // the project list so the phase badge stays in sync.
      qc.invalidateQueries({ queryKey: messagesKey(projectId) });
      qc.invalidateQueries({ queryKey: PROJECTS_KEY });
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
    // exists before then). The endpoint is a 501 stub until Epic 2 — don't
    // retry that (the UI keys NotReady off the error) and don't retry the 403
    // phase gate either; both are deterministic. Real transient failures still
    // get a couple of attempts.
    enabled,
    retry: (count, error) => {
      const status = (error as { response?: { status?: number } })?.response
        ?.status;
      return status !== 501 && status !== 403 && count < 2;
    },
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
  });
}
