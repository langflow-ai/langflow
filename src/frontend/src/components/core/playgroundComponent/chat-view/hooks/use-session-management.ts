import { useEffect, useMemo, useState } from "react";
import { useDeleteSession } from "@/controllers/API/queries/messages/use-delete-sessions";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { useGetFlowId } from "./use-get-flow-id";

//Manages session state and selection logic for the chat view.
//Similar to IOModal's session management but simplified.
export function useSessionManagement(isContainerOpen: boolean) {
  const currentFlowId = useGetFlowId();

  // Fetch sessions only when container is open
  const { data: sessionsData, isLoading: sessionsLoading } =
    useGetSessionsFromFlowQuery(
      {
        id: currentFlowId,
      },
      {
        enabled: isContainerOpen,
        refetchOnWindowFocus: false,
        refetchOnMount: false,
        refetchOnReconnect: false,
      },
    );

  // Current selected session (similar to IOModal's visibleSession)
  const [currentSessionId, setCurrentSessionId] = useState<string | undefined>(
    currentFlowId,
  );

  const { mutate: deleteSession } = useDeleteSession();

  // Process sessions: include default flow ID and ensure no duplicates
  const sessions = useMemo(() => {
    if (!sessionsData?.sessions) {
      return currentFlowId ? [currentFlowId] : [];
    }
    const sessionList = [...sessionsData.sessions];
    if (currentFlowId && !sessionList.includes(currentFlowId)) {
      sessionList.unshift(currentFlowId);
    }
    return sessionList;
  }, [sessionsData?.sessions, currentFlowId]);

  // Auto-select session when sessions are loaded
  // If multiple sessions, select the last one (most recent)
  // Only auto-select if no session is currently selected (prevents resetting manually selected/renamed sessions)
  useEffect(() => {
    if (sessionsLoading) return;

    // Only auto-select if no session is currently selected
    // This prevents resetting manually selected sessions (e.g., after rename)
    if (!currentSessionId) {
      if (sessions.length > 0) {
        // If multiple sessions, select the last one (most recent)
        setCurrentSessionId(sessions[sessions.length - 1]);
      } else if (currentFlowId) {
        // No sessions, default to flow ID
        setCurrentSessionId(currentFlowId);
      }
    }
    // Note: We intentionally don't include currentSessionId in dependencies
    // to avoid resetting manually selected sessions when the sessions list updates
  }, [sessions, sessionsLoading, currentFlowId]);

  const handleSessionSelect = (sessionId: string) => {
    setCurrentSessionId(sessionId);
  };

  const handleNewChat = () => {
    const newSessionName = `Session ${new Date().toLocaleString("en-US", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      second: "2-digit",
      timeZone: "UTC",
    })}`;
    setCurrentSessionId(newSessionName);
    // TODO: Clear messages or reset chat state
  };

  const handleDeleteSession = (sessionId: string) => {
    if (!sessions.includes(sessionId)) return;

    deleteSession(
      { sessionId },
      {
        onSuccess: () => {
          // If deleted session was the current one, switch to another
          if (sessionId === currentSessionId) {
            const remainingSessions = sessions.filter((s) => s !== sessionId);
            if (remainingSessions.length > 0) {
              setCurrentSessionId(
                remainingSessions[remainingSessions.length - 1],
              );
            } else {
              setCurrentSessionId(currentFlowId);
            }
          }
        },
      },
    );
  };

  return {
    currentSessionId,
    sessions,
    isLoading: sessionsLoading,
    handleSessionSelect,
    handleNewChat,
    handleDeleteSession,
    currentFlowId,
  };
}
