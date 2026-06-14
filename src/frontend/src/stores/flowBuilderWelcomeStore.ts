import { create } from "zustand";

/**
 * Coordinates the welcome overlay that surfaces on a freshly-created empty
 * flow with the AssistantPanel hand-off:
 *
 *   - ``isOpen``         — should the overlay render?
 *   - ``pendingMessage`` — when the user submits the textarea, the typed
 *                          text is stashed here so the assistant chat can
 *                          consume it as the first user turn on open.
 *
 * Kept intentionally tiny: this state belongs to ONE feature (the "New Flow"
 * onboarding entry point) and merging it into ``flowsManagerStore`` would
 * couple the overlay's UX to flow-wide concerns it doesn't share.
 */
interface FlowBuilderWelcomeState {
  isOpen: boolean;
  /** When non-null, the assistant panel should auto-send this on next open. */
  pendingMessage: string | null;
  /** The flow id the welcome was opened for. When the user navigates to a
   *  different flow (e.g. picks a template in the TemplatesModal that spins
   *  up a fresh flow), the mount compares this to the current flow id and
   *  auto-closes — otherwise the welcome lingers on top of a freshly-loaded
   *  canvas it doesn't belong to. */
  openedForFlowId: string | null;
  open: (flowId?: string | null) => void;
  close: () => void;
  setPendingMessage: (message: string) => void;
  clearPendingMessage: () => void;
}

const useFlowBuilderWelcomeStore = create<FlowBuilderWelcomeState>((set) => ({
  isOpen: false,
  pendingMessage: null,
  openedForFlowId: null,
  open: (flowId = null) => set({ isOpen: true, openedForFlowId: flowId }),
  // Closing also drops any unconsumed pending message — a stale value would
  // otherwise replay into the assistant the next time the overlay opens.
  close: () =>
    set({ isOpen: false, pendingMessage: null, openedForFlowId: null }),
  setPendingMessage: (message) => set({ pendingMessage: message }),
  clearPendingMessage: () => set({ pendingMessage: null }),
}));

export default useFlowBuilderWelcomeStore;
