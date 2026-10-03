import { create } from "zustand";
import type { HistoryTimeline } from "@/utils/flow-operations/history";

/**
 * Shared by the version sidebar, which owns the selection and draws the
 * previewed flow, and the history slider on the canvas, which moves it.
 */
interface RevisionPlaybackState {
  /** The flow's retained history, replayed; null until loaded. */
  timeline: HistoryTimeline | null;
  /** The revision being previewed; null when not previewing history. */
  revision: number | null;
  /** Previews `revision`. Registered by the version sidebar while it is open. */
  selectRevision: ((revision: number) => void) | null;
  setTimeline: (timeline: HistoryTimeline | null) => void;
  setRevision: (revision: number | null) => void;
  setSelectRevision: (
    selectRevision: ((revision: number) => void) | null,
  ) => void;
}

const useRevisionPlaybackStore = create<RevisionPlaybackState>((set) => ({
  timeline: null,
  revision: null,
  selectRevision: null,
  setTimeline: (timeline) => set({ timeline }),
  setRevision: (revision) => set({ revision }),
  setSelectRevision: (selectRevision) => set({ selectRevision }),
}));

export default useRevisionPlaybackStore;
