import { useMemo } from "react";
import { useCollaborationLocalSelectionStore } from "@/hooks/flows/collaboration-local-selection-store";
import {
  buildCollaborationRosterUserIds,
  buildSelectionIndexesWithLocal,
  resolveNodeCollaborationParticipants,
} from "@/hooks/flows/collaboration-node-participants";
import type { CollaborationSelectionParticipant } from "@/hooks/flows/collaboration-selection-markers";
import { useOptionalFlowCollaborationContext } from "@/hooks/flows/flow-collaboration-context";
import useAuthStore from "@/stores/authStore";

export function useNodeCollaborationParticipants(
  nodeId: string,
): CollaborationSelectionParticipant[] {
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

  return useMemo(() => {
    if (!collaboration?.betaEnabled) {
      return [];
    }

    const { byNodeId } = buildSelectionIndexesWithLocal({
      selectionIndexes: collaboration.selectionIndexes,
      betaEnabled: collaboration.betaEnabled,
      userData,
      localSelection,
      rosterUserIds,
    });

    return resolveNodeCollaborationParticipants(nodeId, byNodeId);
  }, [
    collaboration?.betaEnabled,
    collaboration?.selectionIndexes,
    localSelection,
    nodeId,
    rosterUserIds,
    userData,
  ]);
}
