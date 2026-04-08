import { useEffect, useMemo, useState } from "react";
import { useGetMemorySessions } from "@/controllers/API/queries/memories/use-get-memory-sessions";
import { resolveDefaultSessionId } from "./memorySessionResolverHelpers";

type UseMemorySessionResolverArgs = {
  memoryId?: string | null;
};

export const useMemorySessionResolver = ({
  memoryId,
}: UseMemorySessionResolverArgs) => {
  const [selectedSession, setSelectedSession] = useState<string | null>(null);

  const { data: memorySessions = [], refetch: refetchMemorySessions } =
    useGetMemorySessions(
      { memoryId: memoryId ?? "" },
      {
        enabled: !!memoryId,
        retry: false,
      },
    );

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
      if (prev && sessionIds.includes(prev)) return prev;
      return resolveDefaultSessionId(memorySessions);
    });
  }, [memoryId, memorySessions]);

  const effectiveSessionId = useMemo(() => {
    const candidate = selectedSession?.trim();
    if (candidate) {
      const exists = memorySessions.some((s) => s.session_id === candidate);
      if (exists) return candidate;
    }

    const fallback = resolveDefaultSessionId(memorySessions);
    return fallback && fallback.trim() ? fallback : null;
  }, [selectedSession, memorySessions]);

  return {
    memorySessions,
    selectedSession,
    setSelectedSession,
    effectiveSessionId,
  };
};
