import type { MemorySessionInfo } from "@/controllers/API/queries/memories/types";

export const resolveDefaultSessionId = (sessions: MemorySessionInfo[]) => {
  if (!sessions.length) return null;

  const toTime = (value: string | null | undefined) =>
    value ? new Date(value).getTime() : 0;

  const sorted = [...sessions].sort((a, b) => {
    const timeDiff = toTime(b.last_sync_at) - toTime(a.last_sync_at);
    if (timeDiff !== 0) return timeDiff;
    const pendingDiff = (b.pending_count ?? 0) - (a.pending_count ?? 0);
    if (pendingDiff !== 0) return pendingDiff;
    return (a.session_id ?? "").localeCompare(b.session_id ?? "");
  });

  return sorted[0]?.session_id ?? null;
};
