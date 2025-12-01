import { useEffect, useState } from "react";
import { ChatHeader } from "@/components/core/playgroundComponent/chat-view/chat-header";
import { ChatSidebar } from "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-sidebar";
import { useSessionManagement } from "@/components/core/playgroundComponent/chat-view/hooks/use-session-management";
import { Messages } from "@/components/core/playgroundComponent/chat-view/messages";
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
      <div className="flex-1 flex overflow-hidden">
        {isFullscreen && sidebarOpen && (
          <div className="w-1/5 max-w-[280px] min-w-[250px] border-r border-border bg-background overflow-y-auto">
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
        <div className="flex-1 overflow-auto p-6">
          <Messages
            visibleSession={currentSessionId ?? currentFlowId}
            playgroundPage={true}
          />
        </div>
      </div>
    </div>
  );
}
