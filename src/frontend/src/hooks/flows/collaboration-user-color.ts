const COLLABORATION_USER_COLORS = [
  "#f97316",
  "#22c55e",
  "#3b82f6",
  "#a855f7",
  "#ec4899",
  "#14b8a6",
  "#eab308",
  "#ef4444",
] as const;

function hashUserId(userId: string): number {
  let hash = 0;
  for (let index = 0; index < userId.length; index += 1) {
    hash = (hash * 31 + userId.charCodeAt(index)) >>> 0;
  }
  return hash;
}

/** Stable roster order so collaborators in the same flow get distinct colors. */
export function buildCollaborationColorRoster(
  userIds: Iterable<string>,
): string[] {
  return [...new Set(userIds)].sort((left, right) => left.localeCompare(right));
}

export function getCollaborationUserColor(
  userId: string,
  rosterUserIds?: readonly string[],
): string {
  const roster =
    rosterUserIds && rosterUserIds.length > 0
      ? buildCollaborationColorRoster(rosterUserIds)
      : [userId];
  const index = roster.indexOf(userId);
  const colorIndex =
    index >= 0 ? index : hashUserId(userId) % COLLABORATION_USER_COLORS.length;
  return COLLABORATION_USER_COLORS[
    colorIndex % COLLABORATION_USER_COLORS.length
  ];
}

export function buildCollaborationSelectionOutline(
  colors: string[],
): string | undefined {
  if (colors.length === 0) {
    return undefined;
  }
  if (colors.length === 1) {
    return `0 0 0 2px ${colors[0]}`;
  }
  return colors
    .slice(0, 4)
    .map((color, index) => `0 0 0 ${2 + index * 2}px ${color}`)
    .join(", ");
}
