import { resolveCollaborationSelectionLabel } from "@/hooks/flows/collaboration-selection-labels";
import {
  buildCollaborationColorRoster,
  getCollaborationUserColor,
} from "@/hooks/flows/collaboration-user-color";
import type { AllNodeType, EdgeType } from "@/types/flow";
import type {
  CollaborationCollaboratorRow,
  CollaborationPresenceUser,
  CollaborationSelectionTarget,
  CollaborationUserSelection,
} from "@/types/flow-collaboration";

export function selectionForUser(
  selections: CollaborationUserSelection[],
  userId: string,
): CollaborationSelectionTarget | null {
  return selections.find((entry) => entry.user_id === userId)?.selected ?? null;
}

export type CurrentUserCollaborationProfile = {
  user_id: string;
  username: string;
  profile_image?: string | null;
};

export function buildCollaboratorRows({
  users,
  selections,
  nodes,
  edges,
  currentUserId,
  currentUserProfile,
  localSelectionForCurrentUser,
  labelOptions,
}: {
  users: CollaborationPresenceUser[];
  selections: CollaborationUserSelection[];
  nodes: AllNodeType[];
  edges: EdgeType[];
  currentUserId?: string | null;
  currentUserProfile?: CurrentUserCollaborationProfile | null;
  localSelectionForCurrentUser?: CollaborationSelectionTarget | null;
  labelOptions?: Parameters<typeof resolveCollaborationSelectionLabel>[3];
}): CollaborationCollaboratorRow[] {
  const rosterUsers = [...users];
  if (
    currentUserProfile &&
    !rosterUsers.some((user) => user.user_id === currentUserProfile.user_id)
  ) {
    rosterUsers.unshift({
      user_id: currentUserProfile.user_id,
      username: currentUserProfile.username,
      profile_image: currentUserProfile.profile_image,
    });
  }

  const rosterUserIds = buildCollaborationColorRoster(
    rosterUsers.map((user) => user.user_id),
  );

  const rows = rosterUsers.map((user) => {
    const isCurrentUser = Boolean(
      currentUserId && user.user_id === currentUserId,
    );
    let selected = selectionForUser(selections, user.user_id);
    if (isCurrentUser && localSelectionForCurrentUser !== undefined) {
      selected = localSelectionForCurrentUser;
    }

    return {
      user_id: user.user_id,
      username: user.username,
      profile_image: user.profile_image,
      selected,
      selectionLabel: resolveCollaborationSelectionLabel(
        selected,
        nodes,
        edges,
        labelOptions,
      ),
      isCurrentUser,
      color: getCollaborationUserColor(user.user_id, rosterUserIds),
    };
  });

  return rows.sort((left, right) => {
    if (left.isCurrentUser !== right.isCurrentUser) {
      return left.isCurrentUser ? -1 : 1;
    }
    return left.username.localeCompare(right.username);
  });
}

export function applyPresenceSnapshot(
  _currentUsers: CollaborationPresenceUser[],
  users: CollaborationPresenceUser[],
): CollaborationPresenceUser[] {
  return users.map(({ selected: _selected, ...user }) => ({ ...user }));
}

export function applyPresenceJoined(
  currentUsers: CollaborationPresenceUser[],
  user: CollaborationPresenceUser,
): CollaborationPresenceUser[] {
  const { selected: _selected, ...presenceUser } = user;
  const existingIndex = currentUsers.findIndex(
    (entry) => entry.user_id === presenceUser.user_id,
  );
  if (existingIndex === -1) {
    return [...currentUsers, { ...presenceUser }];
  }

  const nextUsers = [...currentUsers];
  nextUsers[existingIndex] = { ...presenceUser };
  return nextUsers;
}

export function applyPresenceLeft(
  currentUsers: CollaborationPresenceUser[],
  userId: string,
): CollaborationPresenceUser[] {
  return currentUsers.filter((user) => user.user_id !== userId);
}

export function selectionsFromPresenceSnapshot(
  users: CollaborationPresenceUser[],
): CollaborationUserSelection[] {
  return users
    .filter((user) => user.selected != null)
    .map((user) => ({
      user_id: user.user_id,
      selected: user.selected ? { ...user.selected } : null,
    }));
}

export function applySelectionUpdated(
  currentSelections: CollaborationUserSelection[],
  userId: string,
  selected: CollaborationSelectionTarget | null,
): CollaborationUserSelection[] {
  const withoutUser = currentSelections.filter(
    (entry) => entry.user_id !== userId,
  );
  if (selected === null) {
    return withoutUser;
  }
  return [...withoutUser, { user_id: userId, selected: { ...selected } }];
}
