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

const BASE = "/api/v1/lothal/projects/";

const PROJECTS_KEY = ["lothal", "projects"] as const;
const messagesKey = (projectId: string) =>
  ["lothal", "messages", projectId] as const;

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
