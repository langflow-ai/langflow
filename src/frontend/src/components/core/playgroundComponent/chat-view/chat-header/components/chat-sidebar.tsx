import React from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { useGetFlowId } from "../../hooks/use-get-flow-id";
import { SessionSelector } from "./session-selector";

interface ChatSidebarProps {
  onNewChat?: () => void;
  onSessionSelect?: (sessionId: string) => void;
  currentSessionId?: string;
  onDeleteSession?: (sessionId: string) => void;
}

export function ChatSidebar({
  onNewChat,
  onSessionSelect,
  currentSessionId,
  onDeleteSession,
}: ChatSidebarProps) {
  const currentFlowId = useGetFlowId();
  const { data: sessionsData, isLoading } = useGetSessionsFromFlowQuery({
    id: currentFlowId,
  });

  // Use sessions directly from query (it already includes currentFlowId if needed)
  // Ensure currentSessionId is included in the list even if it's not in the API response
  const sessions = React.useMemo(() => {
    const sessionList = sessionsData?.sessions || [];
    console.log("🔍 ChatSidebar - Raw sessions from API:", sessionList);
    // If currentSessionId exists and is not in the list, add it
    if (currentSessionId && !sessionList.includes(currentSessionId)) {
      console.log("➕ Adding currentSessionId to list:", currentSessionId);
      return [currentSessionId, ...sessionList];
    }
    console.log("✅ Final sessions list:", sessionList);
    return sessionList;
  }, [sessionsData?.sessions, currentSessionId]);

  const visibleSession = currentSessionId;

  const handleDeleteSession = (session: string) => {
    onDeleteSession?.(session);
    // If deleted session was the current one, switch to default
    if (session === currentSessionId) {
      onSessionSelect?.(currentFlowId);
    }
  };

  const handleSessionClick = (session: string) => {
    onSessionSelect?.(session);
  };

  return (
    <div className="flex flex-col pl-3">
      <div
        className="flex flex-col pb-2"
        style={{ gap: "var(--space-4, 16px)" }}
      >
        <div className="flex items-center justify-between">
          <div
            className="flex items-center"
            style={{ gap: "var(--space-4, 16px)" }}
          >
            <ForwardedIconComponent
              name="List"
              className="h-[18px] w-[18px] text-ring"
            />
            <div className="text-mmd font-normal">Sessions</div>
          </div>
          <ShadTooltip styleClasses="z-50" content="New Chat">
            <div>
              <Button
                data-testid="new-chat"
                variant="ghost"
                className="flex h-8 w-8 items-center justify-center !p-0 hover:bg-secondary-hover"
                onClick={onNewChat}
              >
                <ForwardedIconComponent
                  name="Plus"
                  className="h-[18px] w-[18px] text-ring"
                />
              </Button>
            </div>
          </ShadTooltip>
        </div>
      </div>
      {isLoading ? (
        <div className="p-4 text-sm text-muted-foreground">Loading...</div>
      ) : (
        <div className="flex flex-col" style={{ gap: "0.5rem" }}>
          {sessions.map((session, index) => (
            <SessionSelector
              key={index}
              session={session}
              currentFlowId={currentFlowId}
              deleteSession={handleDeleteSession}
              toggleVisibility={() => handleSessionClick(session)}
              isVisible={visibleSession === session}
              updateVisibleSession={handleSessionClick}
              inspectSession={(session) => {
                // TODO: Implement session inspection
                console.log("Inspect session:", session);
              }}
              setActiveSession={(session) => {
                // TODO: Implement active session
                console.log("Set active session:", session);
              }}
              selectedView={undefined}
              setSelectedView={() => {}}
              playgroundPage={true}
            />
          ))}
        </div>
      )}
    </div>
  );
}
