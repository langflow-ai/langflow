import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { InteractiveContent } from "@/types/chat";

/**
 * Canvas-side human-in-the-loop state (LE-1603): the single node currently awaiting
 * a human decision, so the Human Input node can show an awaiting badge + an anchored
 * decision popover. Single slot — the default single-node slice pauses one node at a
 * time; the badge component matches on `nodeId`.
 */
interface HitlPending {
  nodeId: string;
  content: InteractiveContent;
}

export interface HitlExecutedOutput {
  id: string;
  name: string;
  latencyMs: number | null;
  outputs: Record<string, unknown>;
}

interface HitlStoreType {
  pending: HitlPending | null;
  setPending: (pending: HitlPending) => void;
  clear: () => void;
  // Resolved decision per trace id so the gate step survives panel reopen (not persisted backend-side).
  resolved: Record<string, string>;
  setResolved: (traceId: string, action: string) => void;
  // Executed output components per trace id (Chat Output), captured from flowPool so the trace keeps
  // showing them after flowPool clears on canvas navigation (also not persisted backend-side).
  executedOutputs: Record<string, HitlExecutedOutput[]>;
  setExecutedOutputs: (traceId: string, outputs: HitlExecutedOutput[]) => void;
}

export const useHitlStore = create<HitlStoreType>()(
  persist(
    (set) => ({
      pending: null,
      setPending: (pending) => set({ pending }),
      clear: () => set({ pending: null }),
      resolved: {},
      setResolved: (traceId, action) =>
        set((state) => ({
          resolved: { ...state.resolved, [traceId]: action },
        })),
      executedOutputs: {},
      setExecutedOutputs: (traceId, outputs) =>
        set((state) => ({
          executedOutputs: { ...state.executedOutputs, [traceId]: outputs },
        })),
    }),
    {
      name: "langflow-hitl-trace",
      storage: createJSONStorage(() => localStorage),
      // Only the trace-display state is durable; the live pending slot is transient per session.
      partialize: (state) => ({
        resolved: state.resolved,
        executedOutputs: state.executedOutputs,
      }),
    },
  ),
);
