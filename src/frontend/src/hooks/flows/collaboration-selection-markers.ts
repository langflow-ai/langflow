import type { CollaborationCollaboratorRow } from "@/types/flow-collaboration";

export type CollaborationSelectionParticipant = Pick<
  CollaborationCollaboratorRow,
  "user_id" | "username" | "profile_image" | "isCurrentUser" | "color"
>;

export type CollaborationSelectionMarker = {
  targetId: string;
  kind: "node" | "edge";
  participants: CollaborationSelectionParticipant[];
};

export function groupCollaboratorsBySelection(
  collaborators: CollaborationCollaboratorRow[],
): CollaborationSelectionMarker[] {
  const markers = new Map<string, CollaborationSelectionMarker>();

  for (const collaborator of collaborators) {
    if (!collaborator.selected) {
      continue;
    }

    const key = `${collaborator.selected.kind}:${collaborator.selected.id}`;
    const existing = markers.get(key);
    const participant: CollaborationSelectionParticipant = {
      user_id: collaborator.user_id,
      username: collaborator.username,
      profile_image: collaborator.profile_image,
      isCurrentUser: collaborator.isCurrentUser,
      color: collaborator.color,
    };

    if (existing) {
      existing.participants.push(participant);
      continue;
    }

    markers.set(key, {
      targetId: collaborator.selected.id,
      kind: collaborator.selected.kind,
      participants: [participant],
    });
  }

  return Array.from(markers.values()).map((marker) => ({
    ...marker,
    participants: marker.participants.sort((left, right) => {
      if (left.isCurrentUser !== right.isCurrentUser) {
        return left.isCurrentUser ? -1 : 1;
      }
      return left.username.localeCompare(right.username);
    }),
  }));
}
