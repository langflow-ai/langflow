import { create } from "zustand";
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

interface HitlStoreType {
  pending: HitlPending | null;
  setPending: (pending: HitlPending) => void;
  clear: () => void;
}

export const useHitlStore = create<HitlStoreType>((set) => ({
  pending: null,
  setPending: (pending) => set({ pending }),
  clear: () => set({ pending: null }),
}));
