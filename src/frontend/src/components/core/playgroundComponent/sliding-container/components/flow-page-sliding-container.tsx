import { useEffect, useMemo, useRef, useState } from "react";
import { ChatHeader } from "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-header";
import { ChatSidebar } from "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-sidebar";
import { useGetFlowId } from "@/components/core/playgroundComponent/hooks/use-get-flow-id";
import { useSimpleSidebar } from "@/components/ui/simple-sidebar";
import { SLIDING_TRANSITION_MS } from "@/constants/constants";
import { useEditSessionInfo } from "../../chat-view/chat-header/hooks/use-edit-session-info";
import { useGetAddSessions } from "../../chat-view/chat-header/hooks/use-get-add-sessions";
import { Messages } from "../../chat-view/messages/messages";

type FlowPageSlidingContainerContentProps = {
  isFullscreen: boolean;
  setIsFullscreen: (value: boolean) => void;
};

export function FlowPageSlidingContainerContent({
  isFullscreen,
  setIsFullscreen,
}: FlowPageSlidingContainerContentProps) {
  const currentFlowId = useGetFlowId();
  const { setOpen, setWidth, fullscreen } = useSimpleSidebar();

  const { sessions: fetchedSessions, addNewSession } = useGetAddSessions({
    flowId: currentFlowId,
  });
  const { handleDelete } = useEditSessionInfo({ flowId: currentFlowId });

  const [currentSessionId, setCurrentSessionId] = useState<string | undefined>(
    currentFlowId,
  );

  const sessions = useMemo(() => {
    const base = new Set<string>(fetchedSessions);
    if (currentFlowId) base.add(currentFlowId);
    if (currentSessionId) base.add(currentSessionId);
    return Array.from(base);
  }, [fetchedSessions, currentFlowId, currentSessionId]);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const transitionTimer = useRef<number | null>(null);

  const startTransitionLock = () => {
    setIsTransitioning(true);
    if (transitionTimer.current) {
      window.clearTimeout(transitionTimer.current);
    }
    transitionTimer.current = window.setTimeout(() => {
      setIsTransitioning(false);
      transitionTimer.current = null;
    }, SLIDING_TRANSITION_MS);
  };

  useEffect(
    () => () => {
      if (transitionTimer.current) {
        window.clearTimeout(transitionTimer.current);
      }
    },
    [],
  );

  // In fullscreen, start immediately but slide in from the right edge.
  useEffect(() => {
    if (!isFullscreen) {
      setSidebarOpen(false);
      return;
    }
    setSidebarOpen(false);
    requestAnimationFrame(() => setSidebarOpen(true));
  }, [isFullscreen]);

  const handleExitFullscreen = () => {
    if (isTransitioning) return;
    startTransitionLock();
    setIsFullscreen(false);
    setOpen(true);
    setWidth(300);
  };

  const handleClose = () => {
    if (isTransitioning) return;
    startTransitionLock();
    setOpen(false);
    setIsFullscreen(false);
  };

  const handleEnterFullscreen = () => {
    if (isTransitioning) return;
    startTransitionLock();
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

  return (
    <div className="h-full w-full bg-background border-l border-transparent shadow-lg flex flex-col relative">
      <div className="flex-1 flex overflow-hidden">
        {isFullscreen && (
          <div
            className="border-r border-border bg-background overflow-hidden"
            style={{
              width: sidebarOpen ? "20%" : "0px",
              minWidth: sidebarOpen ? "360px" : "0px",
              maxWidth: "280px",
              transition: "width 0.3s ease, min-width 0.3s ease",
            }}
          >
            <div className="h-full overflow-y-auto">
              <div className="p-4 pt-[15px]">
                <ChatSidebar
                  sessions={sessions}
                  onNewChat={handleNewChat}
                  onSessionSelect={handleSessionSelect}
                  currentSessionId={currentSessionId}
                  onDeleteSession={handleDeleteSession}
                />
              </div>
            </div>
          </div>
        )}
        <div className="flex-1 flex flex-col overflow-hidden">
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
