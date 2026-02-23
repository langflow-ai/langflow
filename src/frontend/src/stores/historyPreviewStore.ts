import { create } from "zustand";
import type { AllNodeType, EdgeType } from "../types/flow";

interface HistoryPreviewState {
  previewNodes: AllNodeType[] | null;
  previewEdges: EdgeType[] | null;
  previewLabel: string | null;
  /** Monotonically increasing counter — changes on every setPreview call so
   *  it can be used as a React key to force remount even when the label is
   *  the same (e.g. switching away from and back to the same version). */
  previewKey: number;
  setPreview: (
    nodes: AllNodeType[],
    edges: EdgeType[],
    label: string,
  ) => void;
  clearPreview: () => void;
}

const useHistoryPreviewStore = create<HistoryPreviewState>((set, get) => ({
  previewNodes: null,
  previewEdges: null,
  previewLabel: null,
  previewKey: 0,
  setPreview: (nodes, edges, label) =>
    set({
      previewNodes: nodes,
      previewEdges: edges,
      previewLabel: label,
      previewKey: get().previewKey + 1,
    }),
  clearPreview: () =>
    set({ previewNodes: null, previewEdges: null, previewLabel: null }),
}));

export default useHistoryPreviewStore;
