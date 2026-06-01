import type {
  CollaborationPresenceUser,
  CollaborationSelectionTarget,
  CollaborationUserSelection,
} from "@/types/flow-collaboration";

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
