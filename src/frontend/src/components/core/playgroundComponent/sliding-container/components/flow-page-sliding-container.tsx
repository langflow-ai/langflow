import { useEffect, useMemo, useState } from "react";
import { ChatHeader } from "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-header";
import { ChatSidebar } from "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-sidebar";
import { useGetFlowId } from "@/components/core/playgroundComponent/hooks/use-get-flow-id";
import { AnimatedConditional } from "@/components/ui/animated-close";
import { useSimpleSidebar } from "@/components/ui/simple-sidebar";
import { useEditSessionInfo } from "../../chat-view/chat-header/hooks/use-edit-session-info";
import { useGetAddSessions } from "../../chat-view/chat-header/hooks/use-get-add-sessions";
import { Messages } from "../../chat-view/chat-messages";

type FlowPageSlidingContainerContentProps = {
  isFullscreen: boolean;
  setIsFullscreen: (value: boolean) => void;
};

export function FlowPageSlidingContainerContent({
  isFullscreen,
  setIsFullscreen,
}: FlowPageSlidingContainerContentProps) {
  const currentFlowId = useGetFlowId();
  const { setOpen, setWidth } = useSimpleSidebar();

  const { sessions: fetchedSessions, addNewSession } = useGetAddSessions({
    flowId: currentFlowId,
  });
  const { handleDelete } = useEditSessionInfo({ flowId: currentFlowId });

  const [currentSessionId, setCurrentSessionId] = useState<string | undefined>(
    currentFlowId,
  );
  const [openLogsModal, setOpenLogsModal] = useState(false);

  const sessions = useMemo(() => {
    const ordered: string[] = [];
    const seen = new Set<string>();
    const push = (id?: string | null) => {
      const trimmed = id?.trim();
      if (!trimmed || seen.has(trimmed)) return;
      seen.add(trimmed);
      ordered.push(trimmed);
    };
    // Always keep the current flow id first to avoid duplicate "Default Session"
    push(currentFlowId);
    if (fetchedSessions?.length) fetchedSessions.forEach(push);
    push(currentSessionId);
    return ordered;
  }, [fetchedSessions, currentFlowId, currentSessionId]);

  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    setSidebarOpen(isFullscreen);
  }, [isFullscreen]);

  const handleExitFullscreen = () => {
    setIsFullscreen(false);
    setOpen(true);
    setWidth(300);
  };

  const handleClose = () => {
    setOpen(false);
    setIsFullscreen(false);
  };

  const handleEnterFullscreen = () => {
    setIsFullscreen(true);
  };

  const handleSessionSelect = (sessionId: string) => {
    setCurrentSessionId(sessionId);
  };

  const handleNewChat = () => {
    const newId = addNewSession?.() ?? `Session ${sessions.length}`;
    setCurrentSessionId(newId);
  };

  const handleDeleteSession = (sessionId: string) => {
    handleDelete(sessionId);
    if (sessionId === currentSessionId) {
      setCurrentSessionId(currentFlowId);
    }
  };

  const handleOpenLogs = (sessionId: string) => {
    setCurrentSessionId(sessionId);
    setOpenLogsModal(true);
  };

  return (
    <div className="h-full w-full bg-background shadow-lg flex flex-col relative z-[50]">
      <div className="flex-1 flex overflow-hidden">
        <AnimatedConditional isOpen={sidebarOpen}>
          <div className="h-full overflow-y-auto border-r border-border">
            <div className="p-4">
              <ChatSidebar
                sessions={sessions}
                onNewChat={handleNewChat}
                onSessionSelect={handleSessionSelect}
                currentSessionId={currentSessionId}
                onDeleteSession={handleDeleteSession}
                onOpenLogs={handleOpenLogs}
              />
            </div>
          </div>
        </AnimatedConditional>
        <div className="flex-1 flex flex-col overflow-hidden pt-2">
          <ChatHeader
            sessions={sessions}
            onNewChat={handleNewChat}
            onSessionSelect={handleSessionSelect}
            currentSessionId={currentSessionId}
            currentFlowId={currentFlowId}
            onToggleFullscreen={
              isFullscreen ? handleExitFullscreen : handleEnterFullscreen
            }
            isFullscreen={isFullscreen}
            onDeleteSession={handleDeleteSession}
            onClose={handleClose}
            openLogsModal={openLogsModal}
            setOpenLogsModal={setOpenLogsModal}
          />
          <div className="flex-1 overflow-auto p-6">
            <Messages
              visibleSession={currentSessionId ?? currentFlowId ?? null}
              playgroundPage={true}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
