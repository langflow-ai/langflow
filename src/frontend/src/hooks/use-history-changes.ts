import useRevisionPlaybackStore from "@/stores/revisionPlaybackStore";
import { changesAt, type FlowChanges } from "@/utils/flow-operations/changes";

type PlaybackState = ReturnType<typeof useRevisionPlaybackStore.getState>;

/**
 * What the previewed point in history changed. Null unless a point in the
 * flow's history is being previewed, so the live canvas never shows any.
 */
function previewChanges(state: PlaybackState): FlowChanges | null {
  return state.timeline && state.revision !== null
    ? changesAt(state.timeline, state.revision)
    : null;
}

export function usePreviewChanges() {
  return useRevisionPlaybackStore(previewChanges);
}

/** The previewed change to one node; each node re-renders only for its own. */
export function useNodeChange(nodeId: string) {
  return useRevisionPlaybackStore((state) =>
    previewChanges(state)?.nodes.get(nodeId),
  );
}

/** Who last edited one template field at the previewed point. */
export function useFieldChange(nodeId: string, field: string) {
  return useRevisionPlaybackStore((state) =>
    previewChanges(state)?.nodes.get(nodeId)?.fields.get(field),
  );
}

/** Who added an edge at the previewed point. */
export function useEdgeChange(edgeId: string) {
  return useRevisionPlaybackStore((state) =>
    previewChanges(state)?.edges.get(edgeId),
  );
}
