import { useMemo } from "react";
import { useShallow } from "zustand/react/shallow";
import { useCollaborationLocalSelectionStore } from "@/hooks/flows/collaboration-local-selection-store";
import { useOptionalFlowCollaborationContext } from "@/hooks/flows/flow-collaboration-context";
import { buildCollaboratorRows } from "@/hooks/flows/flow-collaboration-state";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import type { CollaborationCollaboratorRow } from "@/types/flow-collaboration";

export function useCollaborationCollaborators(): CollaborationCollaboratorRow[] {
  const collaboration = useOptionalFlowCollaborationContext();
  const userData = useAuthStore((state) => state.userData);
  const localSelection = useCollaborationLocalSelectionStore(
    (state) => state.localSelection,
  );
  const { nodes, edges } = useFlowStore(
    useShallow((state) => ({
      nodes: state.nodes,
      edges: state.edges,
    })),
  );

  return useMemo(() => {
    if (!collaboration?.betaEnabled) {
      return [];
    }

    return buildCollaboratorRows({
      users: collaboration.users,
      selections: collaboration.selections,
      nodes,
      edges,
      currentUserId: userData?.id,
      currentUserProfile: userData
        ? {
            user_id: userData.id,
            username: userData.username,
            profile_image: userData.profile_image,
          }
        : null,
      localSelectionForCurrentUser: localSelection,
    });
  }, [
    collaboration?.betaEnabled,
    collaboration?.selections,
    collaboration?.users,
    edges,
    localSelection,
    nodes,
    userData,
  ]);
}
