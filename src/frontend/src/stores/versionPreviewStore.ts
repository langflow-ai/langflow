import { create } from "zustand";
import type { AllNodeType, EdgeType } from "../types/flow";

interface VersionPreviewState {
  previewNodes: AllNodeType[] | null;
  previewEdges: EdgeType[] | null;
  previewLabel: string | null;
  /** The version entry ID currently being previewed, or null for current draft. */
  previewId: string | null;
  /** True while the sidebar is fetching a version entry to display. */
  isPreviewLoading: boolean;
  /** True after a version was activated via the restore hook. The sidebar
   *  unmount cleanup reads this to avoid overwriting the restored flow. */
  didRestore: boolean;
  setPreviewLoading: (loading: boolean) => void;
  setPreview: (
    nodes: AllNodeType[],
    edges: EdgeType[],
    label: string,
    id?: string | null,
  ) => void;
  clearPreview: () => void;
}

const useVersionPreviewStore = create<VersionPreviewState>((set) => ({
  previewNodes: null,
  previewEdges: null,
  previewLabel: null,
  previewId: null,
  isPreviewLoading: false,
  didRestore: false,
  setPreviewLoading: (loading) => set({ isPreviewLoading: loading }),
  setPreview: (nodes, edges, label, id = null) =>
    set({
      previewNodes: nodes,
      previewEdges: edges,
      previewLabel: label,
      previewId: id,
    }),
  clearPreview: () =>
    set({
      previewNodes: null,
      previewEdges: null,
      previewLabel: null,
      previewId: null,
      isPreviewLoading: false,
      // NOTE: didRestore is intentionally NOT reset here. It is read and
      // reset by the sidebar unmount cleanup, which runs after clearPreview.
    }),
}));

export default useVersionPreviewStore;
