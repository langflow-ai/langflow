import { EdgeLabelRenderer } from "@xyflow/react";
import { useMemo } from "react";
import { useCollaborationLocalSelectionStore } from "@/hooks/flows/collaboration-local-selection-store";
import {
  buildCollaborationRosterUserIds,
  buildSelectionIndexesWithLocal,
} from "@/hooks/flows/collaboration-node-participants";
import { buildCollaborationSelectionOutline } from "@/hooks/flows/collaboration-user-color";
import { useOptionalFlowCollaborationContext } from "@/hooks/flows/flow-collaboration-context";
import { useCollaborationEdgeSelectionTransforms } from "@/hooks/flows/use-collaboration-edge-selection-transforms";
import CollaborationSelectionBump from "@/pages/FlowPage/components/CollaborationSelectionBump";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
export default function CollaborationRemoteSelections(): JSX.Element | null {
  const collaboration = useOptionalFlowCollaborationContext();
  const userData = useAuthStore((state) => state.userData);
  const localSelection = useCollaborationLocalSelectionStore(
    (state) => state.localSelection,
  );

  const rosterUserIds = useMemo(
    () =>
      buildCollaborationRosterUserIds(
        collaboration?.users.map((user) => user.user_id) ?? [],
        userData?.id,
      ),
    [collaboration?.users, userData?.id],
  );

  const selectionIndexes = useMemo(() => {
    if (!collaboration) {
      return { byNodeId: new Map(), byEdgeId: new Map() };
    }

    return buildSelectionIndexesWithLocal({
      selectionIndexes: collaboration.selectionIndexes,
      betaEnabled: collaboration.betaEnabled,
      userData,
      localSelection,
      rosterUserIds,
    });
  }, [collaboration, localSelection, rosterUserIds, userData]);

  const edgeMarkers = useMemo(() => {
    if (!collaboration?.betaEnabled) {
      return [];
    }
    return Array.from(selectionIndexes.byEdgeId.entries()).map(
      ([targetId, participants]) => ({
        targetId,
        kind: "edge" as const,
        participants,
      }),
    );
  }, [collaboration?.betaEnabled, selectionIndexes.byEdgeId]);

  const edges = useFlowStore((state) => state.edges);
  const transforms = useCollaborationEdgeSelectionTransforms(
    edgeMarkers,
    edges,
  );

  if (!collaboration?.betaEnabled || edgeMarkers.length === 0) {
    return null;
  }

  return (
    <EdgeLabelRenderer>
      {edgeMarkers.map((marker) => {
        const transform = transforms.get(marker.targetId);
        if (!transform) {
          return null;
        }

        const outline = buildCollaborationSelectionOutline(
          marker.participants.map((participant) => participant.color),
        );

        return (
          <div
            key={marker.targetId}
            className="pointer-events-auto absolute z-[70]"
            style={{ transform }}
            data-testid={`collaboration-selection-edge-${marker.targetId}`}
          >
            <div className="rounded-full p-0.5" style={{ boxShadow: outline }}>
              <CollaborationSelectionBump participants={marker.participants} />
            </div>
          </div>
        );
      })}
    </EdgeLabelRenderer>
  );
}
