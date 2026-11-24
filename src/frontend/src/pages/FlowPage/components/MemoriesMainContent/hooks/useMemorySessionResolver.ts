import { useEffect, useMemo, useState } from "react";
import type { MemorySessionInfo } from "@/controllers/API/queries/memories/types";
import { useGetMemorySessions } from "@/controllers/API/queries/memories/use-get-memory-sessions";

export const ALL_SESSIONS_VALUE = "__all__";

type UseMemorySessionResolverArgs = {
  memoryId?: string | null;
};

export const useMemorySessionResolver = ({
  memoryId,
}: UseMemorySessionResolverArgs) => {
  const [selectedSession, setSelectedSession] = useState<string | null>(null);

  const {
    data: sessionsInfinite,
    refetch: refetchMemorySessions,
    fetchNextPage: fetchNextSessionsPage,
    hasNextPage: hasNextSessionsPage,
    isFetchingNextPage: isFetchingNextSessionsPage,
  } = useGetMemorySessions(
    { memoryId: memoryId ?? "" },
    {
      enabled: !!memoryId,
    },
  );

  const memorySessions = useMemo<MemorySessionInfo[]>(() => {
    const pages = sessionsInfinite?.pages ?? [];
    return pages.flatMap((p) => p?.items ?? []);
  }, [sessionsInfinite]);

  useEffect(() => {
    setSelectedSession(null);
  }, [memoryId]);

  useEffect(() => {
    if (!memoryId) return;
    if (!selectedSession) return;
    refetchMemorySessions();
  }, [memoryId, selectedSession, refetchMemorySessions]);

  useEffect(() => {
    if (!memoryId) return;
    if (!memorySessions.length) return;

    const sessionIds = memorySessions
      .map((s) => s.session_id)
      .filter((sid): sid is string => !!sid);
    if (!sessionIds.length) return;

    setSelectedSession((prev) => {
      if (prev === ALL_SESSIONS_VALUE) return prev;
      if (prev && sessionIds.includes(prev)) return prev;
      return ALL_SESSIONS_VALUE;
    });
  }, [memoryId, memorySessions]);

  const effectiveSessionId = useMemo(() => {
    if (!selectedSession || selectedSession === ALL_SESSIONS_VALUE) return null;

    const candidate = selectedSession.trim();
    const exists = memorySessions.some((s) => s.session_id === candidate);
    return exists ? candidate : null;
  }, [selectedSession, memorySessions]);

  return {
    memorySessions,
    selectedSession,
    setSelectedSession,
    effectiveSessionId,
    refetchMemorySessions,
    fetchNextSessionsPage,
    hasNextSessionsPage,
    isFetchingNextSessionsPage,
  };
};
