import { useMemo } from "react";
import useFlowStore from "@/stores/flowStore";
import useRevisionPlaybackStore from "@/stores/revisionPlaybackStore";
import type { RevisionEntry } from "@/types/flow/revision";
import { changesAt, type FlowChanges } from "@/utils/flow-operations/changes";
import {
  collectHistoryNames,
  type FlowNames,
  flowNames,
} from "@/utils/flow-operations/names";

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

/** Who added or changed an edge at the previewed point. */
export function useEdgeChange(edgeId: string) {
  return useRevisionPlaybackStore((state) =>
    previewChanges(state)?.edges.get(edgeId),
  );
}

/**
 * Names for the nodes and edges history mentions: from the flow as it is
 * now, then from the replayed history, or, until that has loaded, from
 * `entries`' operations.
 */
export function useFlowNames(entries?: RevisionEntry[]): FlowNames {
  const flowData = useFlowStore((state) => state.currentFlow?.data);
  const timeline = useRevisionPlaybackStore((state) => state.timeline);
  return useMemo(
    () =>
      flowNames(
        flowData,
        timeline?.names ??
          (entries
            ? collectHistoryNames(
                null,
                entries.flatMap((entry) => entry.operations ?? []),
              )
            : null),
      ),
    [flowData, timeline, entries],
  );
}
