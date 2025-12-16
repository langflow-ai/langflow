import React from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { useGetFlowId } from "../../../hooks/use-get-flow-id";
import { useEditSessionInfo } from "../hooks/use-edit-session-info";
import { SessionSelector } from "./session-selector";

interface ChatSidebarProps {
  sessions: string[];
  onNewChat?: () => void;
  onSessionSelect?: (sessionId: string) => void;
  currentSessionId?: string;
  onDeleteSession?: (sessionId: string) => void;
}

export function ChatSidebar({
  sessions,
  onNewChat,
  onSessionSelect,
  currentSessionId,
  onDeleteSession,
}: ChatSidebarProps) {
  const currentFlowId = useGetFlowId();
  const { handleDelete } = useEditSessionInfo({ flowId: currentFlowId });

  const sessionIds = React.useMemo(() => sessions, [sessions]);

  const visibleSession = currentSessionId;

  const handleDeleteSession = (session: string) => {
    handleDelete(session);
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
      {sessionIds.length === 0 ? (
        <div className="p-4 text-sm text-muted-foreground">
          No sessions yet.
        </div>
      ) : (
        <div className="flex flex-col" style={{ gap: "0.5rem" }}>
          {sessionIds.map((session, index) => (
            <SessionSelector
              key={index}
              session={session}
              currentFlowId={currentFlowId}
              deleteSession={handleDeleteSession}
              toggleVisibility={() => handleSessionClick(session)}
              isVisible={visibleSession === session}
              updateVisibleSession={handleSessionClick}
              inspectSession={() => {
                // TODO: Implement session inspection
              }}
              setActiveSession={() => {
                // TODO: Implement active session
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
