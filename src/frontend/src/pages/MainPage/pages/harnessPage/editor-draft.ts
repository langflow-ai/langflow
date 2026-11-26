import useAuthStore from "@/stores/authStore";
import type { ProjectConfig } from "../../entities";

// Only the explicit canvas round trip keeps a draft. Never persist credentials to storage.
const drafts = new Map<string, ProjectConfig>();
const key = (projectId: string) =>
  `${useAuthStore.getState().userData?.id}:${projectId}`;
export const editorDraft = {
  get: (projectId: string) => drafts.get(key(projectId)) ?? {},
  keep: (projectId: string, edits: ProjectConfig) =>
    drafts.set(key(projectId), edits),
  clear: (projectId: string) => drafts.delete(key(projectId)),
};
