import { useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import useFlowStore from "@/stores/flowStore";
import { useGetFlowId } from "../../../hooks/use-get-flow-id";
import { SessionSelector } from "./session-selector";

interface ChatSidebarProps {
  sessions: string[];
  onNewChat?: () => void;
  onSessionSelect?: (sessionId: string) => void;
  currentSessionId?: string;
  onDeleteSession?: (sessionId: string) => void;
  onOpenLogs?: (sessionId: string) => void;
  onRenameSession?: (oldId: string, newId: string) => Promise<void>;
}

export function ChatSidebar({
  sessions,
  onNewChat,
  onSessionSelect,
  currentSessionId,
  onDeleteSession,
  onOpenLogs,
  onRenameSession,
}: ChatSidebarProps) {
  const [openMenuSession, setOpenMenuSession] = useState<string | null>(null);
  const currentFlowId = useGetFlowId();
  const isShareablePlayground = useFlowStore((state) => state.playgroundPage);

  const visibleSession = currentSessionId;

  const handleDeleteSession = (session: string) => {
    onDeleteSession?.(session);
  };

  const handleSessionClick = (session: string) => {
    onSessionSelect?.(session);
  };

  const handleRename = async (sessionId: string, newSessionId: string) => {
    await onRenameSession?.(sessionId, newSessionId);
  };

  return (
    <div className="flex flex-col pb-4 gap-2">
      <div className="flex flex-col">
        <div className="flex h-4 items-center justify-between">
          <div className="px-2 text-xs font-semibold leading-4 text-muted-foreground">
            Sessions
          </div>
          <ShadTooltip
            styleClasses="z-50"
            content="New Chat"
            side={isShareablePlayground ? "bottom" : "top"}
          >
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
      {sessions.length === 0 ? (
        <div className="p-4 text-sm text-muted-foreground">
          No sessions yet.
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          {sessions.map((session) => (
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
              selectedView={undefined}
              setSelectedView={() => {}}
              menuOpen={openMenuSession === session}
              onMenuOpenChange={(open) => {
                setOpenMenuSession(open ? session : null);
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
