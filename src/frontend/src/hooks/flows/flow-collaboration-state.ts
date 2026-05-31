import type {
  CollaborationPresenceUser,
  CollaborationSelectionTarget,
  CollaborationUserSelection,
} from "@/types/flow-collaboration";

export function applyPresenceSnapshot(
  _currentUsers: CollaborationPresenceUser[],
  users: CollaborationPresenceUser[],
): CollaborationPresenceUser[] {
  return users.map((user) => ({ ...user }));
}

export function applyPresenceJoined(
  currentUsers: CollaborationPresenceUser[],
  user: CollaborationPresenceUser,
): CollaborationPresenceUser[] {
  const existingIndex = currentUsers.findIndex(
    (entry) => entry.user_id === user.user_id,
  );
  if (existingIndex === -1) {
    return [...currentUsers, { ...user }];
  }

  const nextUsers = [...currentUsers];
  nextUsers[existingIndex] = { ...user };
  return nextUsers;
}

export function applyPresenceLeft(
  currentUsers: CollaborationPresenceUser[],
  userId: string,
): CollaborationPresenceUser[] {
  return currentUsers.filter((user) => user.user_id !== userId);
}

export function applySelectionSnapshot(
  _currentSelections: CollaborationUserSelection[],
  selections: CollaborationUserSelection[],
): CollaborationUserSelection[] {
  return selections.map((selection) => ({
    user_id: selection.user_id,
    selected: selection.selected ? { ...selection.selected } : null,
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
