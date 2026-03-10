import React, { useMemo } from "react";
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
  onOpenLogs?: (sessionId: string) => void;
  renameLocalSession?: (oldSessionId: string, newSessionId: string) => void;
}

export function ChatSidebar({
  sessions,
  onNewChat,
  onSessionSelect,
  currentSessionId,
  onDeleteSession,
  onOpenLogs,
  renameLocalSession,
}: ChatSidebarProps) {
  const currentFlowId = useGetFlowId();
  const { handleDelete, handleRename } = useEditSessionInfo({
    flowId: currentFlowId,
    renameLocalSession,
  });

  const sessionIds = useMemo(() => sessions, [sessions]);

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
    <div className="flex flex-col pb-4 gap-2">
      <div className="flex flex-col">
        <div className="flex h-4 items-center justify-between">
          <div className="px-2 text-xs font-semibold leading-4 text-muted-foreground">
            Sessions
          </div>
          <ShadTooltip styleClasses="z-50" content="New Chat">
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
          </ShadTooltip>
        </div>
      </div>
      {sessionIds.length === 0 ? (
        <div className="p-4 text-sm text-muted-foreground">
          No sessions yet.
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          {sessionIds.map((session, index) => (
            <SessionSelector
              key={session}
              session={session}
              currentFlowId={currentFlowId}
              deleteSession={handleDeleteSession}
              toggleVisibility={() => handleSessionClick(session)}
              isVisible={visibleSession === session}
              updateVisibleSession={handleSessionClick}
              inspectSession={onOpenLogs}
              handleRename={handleRename}
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
