import { create } from "zustand";
import type { AllNodeType, EdgeType } from "../types/flow";

interface HistoryPreviewState {
  previewNodes: AllNodeType[] | null;
  previewEdges: EdgeType[] | null;
  previewLabel: string | null;
  /** The history entry ID currently being previewed, or null for current draft. */
  previewId: string | null;
  /** Monotonically increasing counter — changes on every setPreview call so
   *  it can be used as a React key to force remount even when the label is
   *  the same (e.g. switching away from and back to the same version). */
  previewKey: number;
  /** True while the sidebar is fetching a history entry to display. */
  isPreviewLoading: boolean;
  setPreviewLoading: (loading: boolean) => void;
  setPreview: (
    nodes: AllNodeType[],
    edges: EdgeType[],
    label: string,
    id?: string | null,
  ) => void;
  clearPreview: () => void;
}

const useHistoryPreviewStore = create<HistoryPreviewState>((set, get) => ({
  previewNodes: null,
  previewEdges: null,
  previewLabel: null,
  previewId: null,
  previewKey: 0,
  isPreviewLoading: false,
  setPreviewLoading: (loading) => set({ isPreviewLoading: loading }),
  setPreview: (nodes, edges, label, id = null) =>
    set({
      previewNodes: nodes,
      previewEdges: edges,
      previewLabel: label,
      previewId: id,
      previewKey: get().previewKey + 1,
    }),
  clearPreview: () =>
    set({
      previewNodes: null,
      previewEdges: null,
      previewLabel: null,
      previewId: null,
      isPreviewLoading: false,
    }),
}));

export default useHistoryPreviewStore;
