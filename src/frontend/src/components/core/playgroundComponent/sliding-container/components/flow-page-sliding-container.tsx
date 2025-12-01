import { useEffect, useState } from "react";
import { StickToBottom } from "use-stick-to-bottom";
import { ChatHeader } from "@/components/core/playgroundComponent/chat-view/chat-header";
import { ChatSidebar } from "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-sidebar";
import { ChatInput } from "@/components/core/playgroundComponent/chat-view/chat-input";
import useDragAndDrop from "@/components/core/playgroundComponent/chat-view/chat-input/hooks/use-drag-and-drop";
import { useSendMessage } from "@/components/core/playgroundComponent/chat-view/hooks/use-send-message";
import { useSessionManagement } from "@/components/core/playgroundComponent/chat-view/hooks/use-session-management";
import { Messages } from "@/components/core/playgroundComponent/chat-view/messages";
import useFlowStore from "@/stores/flowStore";
import type { FilePreviewType } from "@/types/components";
import { useSlidingContainerStore } from "../stores/sliding-container-store";

export function FlowPageSlidingContainerContent() {
  const isFullscreen = useSlidingContainerStore((state) => state.isFullscreen);
  const setIsFullscreen = useSlidingContainerStore(
    (state) => state.setIsFullscreen,
  );
  const setWidth = useSlidingContainerStore((state) => state.setWidth);
  const setIsOpen = useSlidingContainerStore((state) => state.setIsOpen);
  const isOpen = useSlidingContainerStore((state) => state.isOpen);

  // Session management logic extracted to custom hook
  const {
    currentSessionId,
    sessions,
    handleSessionSelect,
    handleNewChat,
    handleDeleteSession,
    currentFlowId,
  } = useSessionManagement(isOpen);

  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Chat input state
  const [files, setFiles] = useState<FilePreviewType[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const { sendMessage } = useSendMessage({ sessionId: currentSessionId });
  const inputs = useFlowStore((state) => state.inputs);
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

  // Auto-open sidebar when entering fullscreen
  useEffect(() => {
    if (isFullscreen) {
      setSidebarOpen(true);
    }
  }, [isFullscreen]);

  const handleExitFullscreen = () => {
    setIsFullscreen(false);
    setIsOpen(true);
    setWidth(300);
  };

  const handleClose = () => {
    setIsOpen(false);
    setIsFullscreen(false);
  };

  return (
    <div
      className="h-full w-full bg-background border-l border-transparent shadow-lg flex"
      onDragOver={dragOver}
      onDragEnter={dragEnter}
      onDragLeave={dragLeave}
      onDrop={onDrop}
    >
      {/* Sidebar */}
      {isFullscreen && sidebarOpen && (
        <div className="w-1/5 max-w-[280px] min-w-[250px] border-r border-border bg-background overflow-y-auto flex-shrink-0">
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

      {/* Chat content area */}
      <div className="flex-1 flex flex-col h-full min-w-0">
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
        <StickToBottom
          className="flex-1 min-h-0 overflow-hidden"
          resize="smooth"
          initial="instant"
        >
          <StickToBottom.Content className="flex flex-col min-h-full overflow-x-hidden p-6">
            <div className="flex flex-col place-self-center max-w-[768px] w-full">
              <Messages
                visibleSession={currentSessionId ?? currentFlowId}
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
  );
}
