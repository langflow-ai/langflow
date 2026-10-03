import { create } from "zustand";
import useFlowStore from "./flowStore";

/**
 * Why the next save of a flow happens, when an action rewrites a component
 * wholesale. The save sends it as `cause`, and the flow's history shows such a
 * change as one line ("Alice updated Agent") instead of every field it wrote.
 * It is a display hint only: nothing checks it.
 */
export type FlowSaveCause = "upgrade_component" | "edit_code";

interface FlowSaveCauseState {
  pending: { flowId: string; cause: FlowSaveCause } | null;
  /** The next save of `flowId` carries `cause`; a later action replaces it. */
  setPendingCause: (flowId: string, cause: FlowSaveCause) => void;
  /** The pending cause for `flowId`, cleared, so only one save carries it. */
  takePendingCause: (flowId: string) => FlowSaveCause | undefined;
}

const useFlowSaveCauseStore = create<FlowSaveCauseState>((set, get) => ({
  pending: null,
  setPendingCause: (flowId, cause) => set({ pending: { flowId, cause } }),
  takePendingCause: (flowId) => {
    const { pending } = get();
    if (!pending) return undefined;
    set({ pending: null });
    // A cause left over from another flow says nothing about this save.
    return pending.flowId === flowId ? pending.cause : undefined;
  },
}));

/** Marks the next save of the flow open in the editor with `cause`. */
export function markNextSaveCause(cause: FlowSaveCause): void {
  const flowId = useFlowStore.getState().currentFlow?.id;
  if (flowId) useFlowSaveCauseStore.getState().setPendingCause(flowId, cause);
}

export default useFlowSaveCauseStore;
