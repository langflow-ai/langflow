import { useEffect, useMemo, useState } from "react";
import { NEW_SESSION_NAME } from "@/constants/constants";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import useFlowStore from "@/stores/flowStore";
import {
  getPlaygroundSessions,
  savePlaygroundSessions,
} from "@/utils/playground-storage";

interface UseGetAddSessionsProps {
  flowId?: string;
  currentSessionId?: string;
}

type UseGetAddSessionsReturnType = (props: UseGetAddSessionsProps) => {
  addNewSession: (allSessions?: string[]) => string;
  removeLocalSession: (sessionId: string) => void;
  renameLocalSession: (oldSessionId: string, newSessionId: string) => void;
  sessions: string[];
  fetchedSessions: string[];
};

export const useGetAddSessions: UseGetAddSessionsReturnType = ({
  flowId,
  currentSessionId,
}) => {
  const { data: dbSessionsResponse } = useGetSessionsFromFlowQuery({
    id: flowId,
  });
  const fetchedSessions = dbSessionsResponse?.sessions ?? [];
  const isPlaygroundPage = useFlowStore((state) => state.playgroundPage);

  const [localSessions, setLocalSessions] = useState<Set<string>>(() => {
    if (!flowId || !isPlaygroundPage) return new Set();
    const stored = getPlaygroundSessions(flowId);
    return stored.length > 0 ? new Set(stored) : new Set();
  });

  // Clean up local sessions that are now persisted (in fetchedSessions)
  useEffect(() => {
    if (localSessions.size === 0) return;
    setLocalSessions((prev) => {
      const updated = new Set(prev);
      let changed = false;
      prev.forEach((session) => {
        // If session is now in fetchedSessions, remove it from localSessions
        if (fetchedSessions.includes(session)) {
          updated.delete(session);
          changed = true;
        }
      });
      return changed ? updated : prev;
    });
  }, [fetchedSessions, localSessions.size]);

  useEffect(() => {
    if (!flowId || !isPlaygroundPage) return;
    savePlaygroundSessions(flowId, Array.from(localSessions));
  }, [localSessions, flowId, isPlaygroundPage]);

  // Merge fetched sessions with local sessions and current session
  const sessions = useMemo(() => {
    const ordered: string[] = [];
    const seen = new Set<string>();
    const push = (id?: string | null) => {
      const trimmed = id?.trim();
      if (!trimmed || seen.has(trimmed)) return;
      seen.add(trimmed);
      ordered.push(trimmed);
    };

    // Add fetched sessions from database/localStorage
    if (fetchedSessions?.length) fetchedSessions.forEach(push);

    // Add all locally created sessions
    Array.from(localSessions).forEach((session) => push(session));

    // Add current session (in case it's not in localSessions or fetchedSessions)
    if (currentSessionId) push(currentSessionId);

    return ordered;
  }, [fetchedSessions, localSessions, currentSessionId]);

  const addNewSession: (allSessions?: string[]) => string = (allSessions) => {
    // Use allSessions if provided (includes currentSessionId), otherwise use merged sessions
    const sessionsToCheck = allSessions ?? sessions;

    // Find the highest number used in "New Session X" pattern
    const newSessionPattern = new RegExp(`^${NEW_SESSION_NAME} (\\d+)$`);
    const existingNumbers = sessionsToCheck
      .map((session) => {
        const match = session.match(newSessionPattern);
        return match ? parseInt(match[1], 10) : -1;
      })
      .filter((num) => num >= 0);

    // Get the next available number
    const nextNumber =
      existingNumbers.length > 0 ? Math.max(...existingNumbers) + 1 : 0;

    const newSessionId = `${NEW_SESSION_NAME} ${nextNumber}`;

    // Add the current session to localSessions before creating new one (if it's a "New Session")
    // Only add if it's not already in localSessions or fetchedSessions to prevent duplicates
    if (
      currentSessionId &&
      currentSessionId.match(newSessionPattern) &&
      !localSessions.has(currentSessionId) &&
      !fetchedSessions.includes(currentSessionId)
    ) {
      setLocalSessions(
        (prev) => new Set([...Array.from(prev), currentSessionId]),
      );
    }

    // Add the new session to localSessions
    setLocalSessions((prev) => new Set([...Array.from(prev), newSessionId]));

    return newSessionId;
  };

  const removeLocalSession = (sessionId: string) => {
    setLocalSessions((prev) => {
      const updated = new Set(prev);
      updated.delete(sessionId);
      return updated;
    });
  };

  const renameLocalSession = (oldSessionId: string, newSessionId: string) => {
    setLocalSessions((prev) => {
      const updated = new Set(prev);
      // Remove old session name and add new one
      const hadOld = updated.delete(oldSessionId);
      updated.add(newSessionId);
      return updated;
    });
  };

  const stableSessions = useMemo(() => [...sessions], [sessions]);

  return {
    addNewSession,
    removeLocalSession,
    renameLocalSession,
    sessions: stableSessions,
    fetchedSessions,
  };
};
