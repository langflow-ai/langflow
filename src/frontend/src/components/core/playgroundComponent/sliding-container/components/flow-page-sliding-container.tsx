import { useEffect, useMemo, useState } from "react";
import { StickToBottom } from "use-stick-to-bottom";
import { ChatHeader } from "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-header";
import { ChatSidebar } from "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-sidebar";
import { useSendMessage } from "@/components/core/playgroundComponent/chat-view/hooks/use-send-message";
import { useGetFlowId } from "@/components/core/playgroundComponent/hooks/use-get-flow-id";
import { AnimatedConditional } from "@/components/ui/animated-close";
import { useSimpleSidebar } from "@/components/ui/simple-sidebar";
import useFlowStore from "@/stores/flowStore";
import type { FilePreviewType } from "@/types/components";
import { useEditSessionInfo } from "../../chat-view/chat-header/hooks/use-edit-session-info";
import { useGetAddSessions } from "../../chat-view/chat-header/hooks/use-get-add-sessions";
import { ChatInput } from "../../chat-view/chat-input";
import useDragAndDrop from "../../chat-view/chat-input/hooks/use-drag-and-drop";
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
  const inputs = useFlowStore((state) => state.inputs);

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
  const [files, setFiles] = useState<FilePreviewType[]>([]);
  const [isDragging, setIsDragging] = useState(false);

  const { sendMessage } = useSendMessage({ sessionId: currentSessionId });
  const inputTypes = inputs.map((obj) => obj.type);
  const noInput = !inputTypes.includes("ChatInput");

  const { dragOver, dragEnter, dragLeave } = useDragAndDrop(
    setIsDragging,
    true,
  );

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  // On initial mount ensure sidebar is closed unless explicitly fullscreen.
  useEffect(() => {
    if (!isFullscreen) {
      setOpen(false);
      setSidebarOpen(false);
    }
  }, [isFullscreen, setOpen]);

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
    <div
      className="h-full w-full bg-background shadow-lg flex flex-col relative z-[50]"
      onDragOver={dragOver}
      onDragEnter={dragEnter}
      onDragLeave={dragLeave}
      onDrop={onDrop}
    >
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
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            <StickToBottom
              className="flex-1 min-h-0 overflow-hidden"
              resize="smooth"
              initial="instant"
            >
              <StickToBottom.Content className="flex flex-col min-h-full overflow-x-hidden p-6">
                <div className="flex flex-col place-self-center max-w-[768px] w-full">
                  <Messages
                    visibleSession={currentSessionId ?? currentFlowId ?? null}
                    playgroundPage={true}
                  />
                </div>
              </StickToBottom.Content>
            </StickToBottom>

            <div
              className={`flex-shrink-0 p-4 ${isFullscreen ? "flex justify-center" : ""}`}
            >
              <div className={isFullscreen ? "w-full max-w-[744px]" : "w-full"}>
                <ChatInput
                  noInput={noInput}
                  files={files}
                  setFiles={setFiles}
                  isDragging={isDragging}
                  playgroundPage={true}
                  sendMessage={sendMessage}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
