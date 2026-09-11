import { create } from "zustand";
import type { FlowType } from "@/types/flow";

/**
 * The state a flow enters when a save is refused because someone else changed it.
 *
 * Once here, saving to the original is over: the only way forward is a duplicate.
 * That is why this is set once and cleared explicitly rather than retried — a
 * conflict that resolves itself would let an autosave overwrite the other person
 * moments after telling the user it could not.
 */

export type ConflictAuthor = {
  id: string | null;
  username: string | null;
};

/** The 409 body the server sends when a save is refused. */
export type ConflictDetail = {
  code: string;
  message?: string;
  flow_id?: string;
  expected_version_token?: string | null;
  current_version_token?: string | null;
  modified_by?: { id: string | null; username: string | null };
  modified_at?: string | null;
};

export type FlowConflict = {
  flowId: string;
  author: ConflictAuthor;
  /** True when the other writer is the current user — a second tab, not a colleague. */
  isSelf: boolean;
  modifiedAt: string | null;
  expectedToken: string | null;
  currentToken: string | null;
  /** The server's version of the flow, fetched once so the dialog can diff against it. */
  theirFlow: FlowType | null;
};

type FlowConflictStoreType = {
  conflict: FlowConflict | null;
  dialogOpen: boolean;
  /** Flows whose conflict ended in a duplicate; they must never be written again. */
  abandonedFlowIds: Set<string>;
  setConflict: (conflict: FlowConflict) => void;
  /** Replace a standing conflict whose token the server has already moved past. */
  refreshConflict: (conflict: FlowConflict) => void;
  setTheirFlow: (flow: FlowType) => void;
  openDialog: () => void;
  closeDialog: () => void;
  clearConflict: () => void;
  abandonFlow: (flowId: string) => void;
  /** Undo an abandonment, because the flow was opened again with a current baseline. */
  resumeFlow: (flowId: string) => void;
};

export const useFlowConflictStore = create<FlowConflictStoreType>(
  (set, get) => ({
    conflict: null,
    dialogOpen: false,
    abandonedFlowIds: new Set<string>(),
    setConflict: (conflict) => {
      // Keep the first conflict. A later one carries the same verdict and replacing it
      // would swap the author's name out from under a dialog someone is reading.
      // Deliberately overwriting a newer version is the exception -- see refreshConflict.
      if (get().conflict?.flowId === conflict.flowId) return;
      if (get().abandonedFlowIds.has(conflict.flowId)) return;
      set({ conflict, dialogOpen: false });
    },
    refreshConflict: (conflict) => {
      // The one case that must replace a standing conflict: an overwrite was
      // refused because the flow moved again, so the token the dialog would send
      // is stale. Keeping the first conflict here would leave the person retrying
      // a write the server can only ever refuse.
      if (get().abandonedFlowIds.has(conflict.flowId)) return;
      set({ conflict });
    },
    setTheirFlow: (flow) => {
      const current = get().conflict;
      if (!current) return;
      set({ conflict: { ...current, theirFlow: flow } });
    },
    openDialog: () => set({ dialogOpen: true }),
    closeDialog: () => set({ dialogOpen: false }),
    clearConflict: () => set({ conflict: null, dialogOpen: false }),
    resumeFlow: (flowId) =>
      set((state) => {
        if (!state.abandonedFlowIds.has(flowId)) return state;
        const next = new Set(state.abandonedFlowIds);
        next.delete(flowId);
        return { abandonedFlowIds: next };
      }),
    abandonFlow: (flowId) =>
      set((state) => ({
        conflict: null,
        dialogOpen: false,
        abandonedFlowIds: new Set(state.abandonedFlowIds).add(flowId),
      })),
  }),
);

export default useFlowConflictStore;
