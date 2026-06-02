import type { CollaborationSelectionIndexes } from "@/hooks/flows/collaboration-selection-indexes";
import type { CollaborationSelectionParticipant } from "@/hooks/flows/collaboration-selection-markers";
import {
  buildCollaborationColorRoster,
  getCollaborationUserColor,
} from "@/hooks/flows/collaboration-user-color";
import type { CollaborationSelectionTarget } from "@/types/flow-collaboration";

export function removeParticipantFromNodeSelectionMap(
  selectionMap: Map<string, CollaborationSelectionParticipant[]>,
  userId: string,
): void {
  for (const [targetId, participants] of selectionMap.entries()) {
    const nextParticipants = participants.filter(
      (participant) => participant.user_id !== userId,
    );
    if (nextParticipants.length === 0) {
      selectionMap.delete(targetId);
    } else if (nextParticipants.length !== participants.length) {
      selectionMap.set(targetId, nextParticipants);
    }
  }
}

export function buildSelectionIndexesWithLocal({
  selectionIndexes,
  betaEnabled,
  userData,
  localSelection,
  rosterUserIds,
}: {
  selectionIndexes: CollaborationSelectionIndexes;
  betaEnabled: boolean;
  userData?: {
    id: string;
    username: string;
    profile_image?: string | null;
  } | null;
  localSelection: CollaborationSelectionTarget | null;
  rosterUserIds: string[];
}): CollaborationSelectionIndexes {
  const byNodeId = new Map(selectionIndexes.byNodeId);
  const byEdgeId = new Map(selectionIndexes.byEdgeId);

  if (!betaEnabled || !userData || !localSelection) {
    return { byNodeId, byEdgeId };
  }

  removeParticipantFromNodeSelectionMap(byNodeId, userData.id);
  removeParticipantFromNodeSelectionMap(byEdgeId, userData.id);

  const participant: CollaborationSelectionParticipant = {
    user_id: userData.id,
    username: userData.username,
    profile_image: userData.profile_image,
    isCurrentUser: true,
    color: getCollaborationUserColor(userData.id, rosterUserIds),
  };
  const targetMap = localSelection.kind === "node" ? byNodeId : byEdgeId;
  const existing = targetMap.get(localSelection.id) ?? [];
  targetMap.set(localSelection.id, [
    participant,
    ...existing.filter((entry) => entry.user_id !== userData.id),
  ]);

  return { byNodeId, byEdgeId };
}

export function resolveNodeCollaborationParticipants(
  nodeId: string,
  byNodeId: ReadonlyMap<string, CollaborationSelectionParticipant[]>,
): CollaborationSelectionParticipant[] {
  return byNodeId.get(nodeId) ?? [];
}

/** Selection chrome is rendered on the node when the current user hosts that selection. */
export function isNodeSelectionHostedInChrome(
  nodeId: string,
  localSelection: CollaborationSelectionTarget | null,
): boolean {
  return localSelection?.kind === "node" && localSelection.id === nodeId;
}

export function buildCollaborationRosterUserIds(
  collaborationUserIds: string[],
  currentUserId?: string | null,
): string[] {
  return buildCollaborationColorRoster([
    ...collaborationUserIds,
    ...(currentUserId ? [currentUserId] : []),
  ]);
}
