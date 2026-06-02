import {
  type CollaborationSelectionParticipant,
  groupCollaboratorsBySelection,
} from "@/hooks/flows/collaboration-selection-markers";
import {
  buildCollaboratorRows,
  type CurrentUserCollaborationProfile,
} from "@/hooks/flows/flow-collaboration-state";
import type {
  CollaborationPresenceUser,
  CollaborationSelectionTarget,
  CollaborationUserSelection,
} from "@/types/flow-collaboration";

export type CollaborationSelectionIndexes = {
  byNodeId: ReadonlyMap<string, CollaborationSelectionParticipant[]>;
  byEdgeId: ReadonlyMap<string, CollaborationSelectionParticipant[]>;
};

export function buildCollaborationSelectionIndexes({
  users,
  selections,
  currentUserId,
  currentUserProfile,
  localSelectionForCurrentUser,
}: {
  users: CollaborationPresenceUser[];
  selections: CollaborationUserSelection[];
  currentUserId?: string | null;
  currentUserProfile?: CurrentUserCollaborationProfile | null;
  localSelectionForCurrentUser?: CollaborationSelectionTarget | null;
}): CollaborationSelectionIndexes {
  const rows = buildCollaboratorRows({
    users,
    selections,
    nodes: [],
    edges: [],
    currentUserId,
    currentUserProfile,
    localSelectionForCurrentUser,
  });

  const byNodeId = new Map<string, CollaborationSelectionParticipant[]>();
  const byEdgeId = new Map<string, CollaborationSelectionParticipant[]>();

  for (const marker of groupCollaboratorsBySelection(rows)) {
    if (marker.kind === "node") {
      byNodeId.set(marker.targetId, marker.participants);
    } else {
      byEdgeId.set(marker.targetId, marker.participants);
    }
  }

  return { byNodeId, byEdgeId };
}
