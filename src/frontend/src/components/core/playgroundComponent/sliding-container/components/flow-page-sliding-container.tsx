import { useEffect, useMemo, useState } from "react";
import { ChatHeader } from "@/components/core/playgroundComponent/chat-view/chat-header";
import { ChatSidebar } from "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-sidebar";
import { useGetFlowId } from "@/components/core/playgroundComponent/chat-view/hooks/use-get-flow-id";
import { useDeleteSession } from "@/controllers/API/queries/messages/use-delete-sessions";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { useSlidingContainerStore } from "../stores/sliding-container-store";

export function FlowPageSlidingContainerContent() {
  const isFullscreen = useSlidingContainerStore((state) => state.isFullscreen);
  const setIsFullscreen = useSlidingContainerStore(
    (state) => state.setIsFullscreen,
  );
  const setWidth = useSlidingContainerStore((state) => state.setWidth);
  const setIsOpen = useSlidingContainerStore((state) => state.setIsOpen);
  const isOpen = useSlidingContainerStore((state) => state.isOpen);
  const currentFlowId = useGetFlowId();

  // Fetch sessions - only when container is open (similar to IOModal)
  // Don't refetch on window focus or when expanding - only when container opens or explicitly invalidated
  const { data: sessionsData, isLoading: sessionsLoading } =
    useGetSessionsFromFlowQuery(
      {
        id: currentFlowId,
      },
      {
        enabled: isOpen,
        refetchOnWindowFocus: false,
        refetchOnMount: false,
        refetchOnReconnect: false,
      },
    );

  const [currentSessionId, setCurrentSessionId] = useState<string | undefined>(
    currentFlowId,
  );
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // Track if currentSessionId was manually set (e.g., after rename) to prevent auto-reset
  const [isManuallySet, setIsManuallySet] = useState(false);
  // Track renamed sessions that aren't in the API response yet
  const [renamedSessions, setRenamedSessions] = useState<Set<string>>(
    new Set(),
  );
  const { mutate: deleteSession } = useDeleteSession();

  const sessions = useMemo(() => {
    if (!sessionsData?.sessions) {
      return [];
    }
    const sessionList = [...sessionsData.sessions];
    // Always include the currentFlowId as the default session if it's not already present
    if (currentFlowId && !sessionList.includes(currentFlowId)) {
      sessionList.unshift(currentFlowId);
    }
    // Include renamed sessions that aren't in the API response yet
    renamedSessions.forEach((sessionId) => {
      if (!sessionList.includes(sessionId)) {
        sessionList.push(sessionId);
      }
    });
    return sessionList;
  }, [sessionsData?.sessions, currentFlowId, renamedSessions]);

  // Determine which session to display: if multiple sessions, show the last one, otherwise show selected or default
  // Only auto-update if currentSessionId is not set or was not manually set
  // Don't override manually selected sessions (e.g., after rename)
  useEffect(() => {
    if (sessionsLoading) return;

    // Only auto-update if currentSessionId is undefined or was not manually set
    // This prevents overriding manually set session IDs (e.g., after rename)
    // IMPORTANT: If isManuallySet is true, NEVER auto-update, even if the session isn't in the list
    if (!currentSessionId || !isManuallySet) {
      if (sessions.length > 0) {
        // If we have multiple sessions, show the last one (most recent)
        if (sessions.length > 1) {
          setCurrentSessionId(sessions[sessions.length - 1]);
        } else {
          // If only one session, show it
          setCurrentSessionId(sessions[0]);
        }
        setIsManuallySet(false); // Reset flag after auto-update
      } else {
        // No sessions, default to flow ID
        setCurrentSessionId(currentFlowId);
        setIsManuallySet(false); // Reset flag after auto-update
      }
    }
    // Note: We intentionally don't include currentSessionId in dependencies
    // to avoid resetting manually selected sessions when the sessions list updates
    // Also note: isManuallySet being true means we should NEVER auto-update
  }, [sessions, sessionsLoading, currentFlowId]);

  // Auto-open sidebar when entering fullscreen
  // Don't reset isManuallySet when expanding - preserve renamed sessions
  useEffect(() => {
    if (isFullscreen) {
      setSidebarOpen(true);
    }
  }, [isFullscreen]);

  const handleNewChat = () => {
    // Create a new session name for the new chat
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
    setIsManuallySet(true); // Mark as manually set
    // TODO: Clear messages or reset chat state
  };

  const handleSessionSelect = (sessionId: string) => {
    setCurrentSessionId(sessionId);
    setIsManuallySet(true); // Mark as manually set (important for rename)
    // If this is a renamed session (not in the original sessions list), track it
    const originalSessions = sessionsData?.sessions || [];
    if (!originalSessions.includes(sessionId) && sessionId !== currentFlowId) {
      setRenamedSessions((prev) => new Set(prev).add(sessionId));
    }
    // TODO: Load messages for selected session
  };

  const handleDeleteSession = (sessionId: string) => {
    // Only delete if session exists in the sessions list
    if (!sessions.includes(sessionId)) {
      return;
    }

    deleteSession(
      { sessionId },
      {
        onSuccess: () => {
          // If deleted session was the current one, switch to another session
          if (sessionId === currentSessionId) {
            const remainingSessions = sessions.filter((s) => s !== sessionId);
            if (remainingSessions.length > 0) {
              // If multiple sessions remain, show the last one
              setCurrentSessionId(
                remainingSessions[remainingSessions.length - 1],
              );
            } else {
              // Otherwise, default to flow ID
              setCurrentSessionId(currentFlowId);
            }
          }
        },
        onError: () => {
          // Error handling can be added here if needed
        },
      },
    );
  };

  const handleExitFullscreen = () => {
    setIsFullscreen(false);
    // Ensure panel stays open and restore to initial width (MIN_WIDTH = 300px)
    setIsOpen(true);
    setWidth(300);
  };

  const handleClose = () => {
    // Close the panel completely
    setIsOpen(false);
    setIsFullscreen(false);
  };

  return (
    <div className="h-full w-full bg-background border-l border-transparent shadow-lg flex flex-col relative">
      <ChatHeader
        onNewChat={handleNewChat}
        onSessionSelect={handleSessionSelect}
        currentSessionId={currentSessionId}
        currentFlowId={currentFlowId}
        onToggleFullscreen={
          isFullscreen ? handleExitFullscreen : () => setIsFullscreen(true)
        }
        isFullscreen={isFullscreen}
        onDeleteSession={handleDeleteSession}
        onClose={handleClose}
      />
      {isFullscreen && sidebarOpen && (
        <div className="absolute left-0 top-0 z-50 h-full w-1/5 max-w-[280px] border-r border-border bg-background overflow-y-auto">
          <div className="p-4 pt-[15px]">
            <ChatSidebar
              onNewChat={handleNewChat}
              onSessionSelect={handleSessionSelect}
              currentSessionId={currentSessionId}
              onDeleteSession={handleDeleteSession}
            />
          </div>
        </div>
      )}
      <div
        className="flex-1 overflow-auto p-6"
        style={
          isFullscreen && sidebarOpen
            ? { marginLeft: "max(20%, 280px)" }
            : undefined
        }
      >
        {/* Content will be added here */}
      </div>
    </div>
  );
}
