import { useEffect, useRef, useState } from "react";
import { StickToBottom, useStickToBottom } from "use-stick-to-bottom";
import { SafariScrollFix } from "@/components/common/safari-scroll-fix";
import { ChatHeader } from "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-header";
import { ChatSidebar } from "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-sidebar";
import { useSendMessage } from "@/components/core/playgroundComponent/chat-view/hooks/use-send-message";
import { useGetFlowId } from "@/components/core/playgroundComponent/hooks/use-get-flow-id";
import { AnimatedConditional } from "@/components/ui/animated-close";
import { useSimpleSidebar } from "@/components/ui/simple-sidebar";
import useFlowStore from "@/stores/flowStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { FilePreviewType } from "@/types/components";
import { ChatInput } from "../../chat-view/chat-input";
import useDragAndDrop from "../../chat-view/chat-input/hooks/use-drag-and-drop";
import { Messages } from "../../chat-view/chat-messages";
import { useChatHistory } from "../../chat-view/chat-messages/hooks/use-chat-history";
import { useSessionManager } from "../../hooks/use-session-manager";

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
  const nodes = useFlowStore((state) => state.nodes);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const setChatValueStore = useUtilityStore((state) => state.setChatValueStore);

  const {
    activeSessionId,
    sessions,
    createSession,
    deleteSession,
    renameSession,
    selectSession,
    clearDefaultSession,
  } = useSessionManager({ flowId: currentFlowId });

  const [openLogsModal, setOpenLogsModal] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [files, setFiles] = useState<FilePreviewType[]>([]);
  const [isDragging, setIsDragging] = useState(false);

  const { sendMessage } = useSendMessage({ sessionId: activeSessionId });
  const inputTypes = inputs.map((obj) => obj.type);
  const noInput = !inputTypes.includes("ChatInput");

  const chatHistory = useChatHistory(activeSessionId ?? currentFlowId ?? null);

  useEffect(() => {
    const chatInput = inputs.find((input) => input.type === "ChatInput");
    const chatInputNode = nodes.find((node) => node.id === chatInput?.id);

    if (chatHistory.length === 0 && !isBuilding && chatInputNode) {
      setChatValueStore(
        chatInputNode.data.node.template["input_value"].value ?? "",
      );
    }
  }, [chatHistory.length, isBuilding, inputs, nodes, setChatValueStore]);

  const stickyInstance = useStickToBottom({
    resize: "instant",
    initial: "instant",
  });

  const prevChatLenRef = useRef(chatHistory.length);
  useEffect(() => {
    if (chatHistory.length > prevChatLenRef.current) {
      const lastMsg = chatHistory[chatHistory.length - 1];
      if (lastMsg?.isSend) {
        window.dispatchEvent(new Event("langflow-scroll-to-bottom"));
        stickyInstance.scrollToBottom("smooth");
      }
    }
    prevChatLenRef.current = chatHistory.length;
  }, [chatHistory, stickyInstance]);

  const { dragOver, dragEnter, dragLeave } = useDragAndDrop(
    setIsDragging,
    true,
  );

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [setOpen]);

  useEffect(() => {
    setSidebarOpen(isFullscreen);
  }, [isFullscreen]);

  const handleExitFullscreen = () => {
    setIsFullscreen(false);
    setOpen(true);
    setWidth(218);
  };

  const handleClose = () => {
    setOpen(false);
  };

  const handleEnterFullscreen = () => {
    setIsFullscreen(true);
  };

  const handleOpenLogs = (sessionId: string) => {
    selectSession(sessionId);
    setOpenLogsModal(true);
  };

  return (
    <div
      className="h-full w-full muted shadow-lg flex flex-col relative z-[50] @container/chat-panel"
      onDragOver={dragOver}
      onDragEnter={dragEnter}
      onDragLeave={dragLeave}
      onDrop={onDrop}
    >
      <div className="flex-1 flex overflow-hidden">
        <AnimatedConditional isOpen={sidebarOpen} width="236px">
          <div className="h-full overflow-y-auto border-r border-border w-218 bg-primary-foreground">
            <div className="p-4">
              <ChatSidebar
                sessions={sessions}
                onNewChat={createSession}
                onSessionSelect={selectSession}
                currentSessionId={activeSessionId}
                onDeleteSession={deleteSession}
                onOpenLogs={handleOpenLogs}
                onRenameSession={renameSession}
              />
            </div>
          </div>
        </AnimatedConditional>
        <div className="flex-1 flex flex-col overflow-hidden pt-2">
          <ChatHeader
            sessions={sessions}
            onNewChat={createSession}
            onSessionSelect={selectSession}
            currentSessionId={activeSessionId}
            currentFlowId={currentFlowId}
            onToggleFullscreen={
              isFullscreen ? handleExitFullscreen : handleEnterFullscreen
            }
            isFullscreen={isFullscreen}
            onDeleteSession={deleteSession}
            onClose={handleClose}
            openLogsModal={openLogsModal}
            setOpenLogsModal={setOpenLogsModal}
            onRenameSession={renameSession}
            onClearChat={clearDefaultSession}
          />
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden playground-messages-wrapper">
            <StickToBottom
              instance={stickyInstance}
              className="flex-1 min-h-0 overflow-hidden"
            >
              <StickToBottom.Content className="flex flex-col min-h-full overflow-x-hidden ">
                <div
                  className={`flex flex-col ${isFullscreen ? "w-full max-w-[744px] p-0 mx-auto" : "w-full"}`}
                >
                  <Messages
                    visibleSession={activeSessionId ?? currentFlowId ?? null}
                    playgroundPage={true}
                  />
                </div>
              </StickToBottom.Content>
              <SafariScrollFix />
            </StickToBottom>

            <div
              className={`flex-shrink-0 p-4 ${isFullscreen ? "flex justify-center" : ""}`}
            >
              <div
                className={`${isFullscreen ? "w-full max-w-[744px]" : "w-full"} p-0`}
              >
                <ChatInput
                  noInput={noInput}
                  files={files}
                  setFiles={setFiles}
                  isDragging={isDragging}
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
