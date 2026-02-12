import { useEffect, useMemo, useState } from "react";
import { StickToBottom } from "use-stick-to-bottom";
import { ChatHeader } from "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-header";
import { ChatSidebar } from "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-sidebar";
import { useSendMessage } from "@/components/core/playgroundComponent/chat-view/hooks/use-send-message";
import { useGetFlowId } from "@/components/core/playgroundComponent/hooks/use-get-flow-id";
import { AnimatedConditional } from "@/components/ui/animated-close";
import { useSimpleSidebar } from "@/components/ui/simple-sidebar";
import {
  CHAT_CONTENT_MAX_WIDTH,
  FOCUS_DELAY_MS,
  SESSION_SIDEBAR_WIDTH,
} from "@/constants/constants";
import useFlowStore from "@/stores/flowStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { FilePreviewType } from "@/types/components";
import { cn } from "@/utils/utils";
import { useEditSessionInfo } from "../../chat-view/chat-header/hooks/use-edit-session-info";
import { useGetAddSessions } from "../../chat-view/chat-header/hooks/use-get-add-sessions";
import { ChatInput } from "../../chat-view/chat-input";
import useDragAndDrop from "../../chat-view/chat-input/hooks/use-drag-and-drop";
import { Messages } from "../../chat-view/chat-messages";
import { useChatHistory } from "../../chat-view/chat-messages/hooks/use-chat-history";

type FlowPageSlidingContainerContentProps = {
  isFullscreen: boolean;
  setIsFullscreen: (value: boolean) => void;
};

export function FlowPageSlidingContainerContent({
  isFullscreen,
  setIsFullscreen,
}: FlowPageSlidingContainerContentProps) {
  const currentFlowId = useGetFlowId();
  const { setOpen } = useSimpleSidebar();
  const inputs = useFlowStore((state) => state.inputs);
  const nodes = useFlowStore((state) => state.nodes);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const setChatValueStore = useUtilityStore((state) => state.setChatValueStore);

  const [currentSessionId, setCurrentSessionId] = useState<string | undefined>(
    currentFlowId,
  );
  const [openLogsModal, setOpenLogsModal] = useState(false);

  const {
    sessions,
    addNewSession,
    removeLocalSession,
    renameLocalSession,
    fetchedSessions,
  } = useGetAddSessions({
    flowId: currentFlowId,
    currentSessionId,
  });
  const { handleDelete } = useEditSessionInfo({
    flowId: currentFlowId,
    dbSessions: fetchedSessions,
    renameLocalSession,
  });

  const orderedSessions = useMemo(() => {
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
    // Add all other sessions
    sessions.forEach(push);
    return ordered;
  }, [sessions, currentFlowId]);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [files, setFiles] = useState<FilePreviewType[]>([]);
  const [isDragging, setIsDragging] = useState(false);

  const { sendMessage } = useSendMessage({ sessionId: currentSessionId });
  const inputTypes = inputs.map((obj) => obj.type);
  const noInput = !inputTypes.includes("ChatInput");

  const chatHistory = useChatHistory(currentSessionId ?? currentFlowId ?? null);

  useEffect(() => {
    const chatInput = inputs.find((input) => input.type === "ChatInput");
    const chatInputNode = nodes.find((node) => node.id === chatInput?.id);

    if (chatHistory.length === 0 && !isBuilding && chatInputNode) {
      setChatValueStore(
        chatInputNode.data.node.template["input_value"].value ?? "",
      );
    }
  }, [chatHistory.length, isBuilding, inputs, nodes, setChatValueStore]);

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
    setSidebarOpen(isFullscreen);
  }, [isFullscreen]);

  const handleClose = () => {
    setOpen(false);
  };

  const handleSessionSelect = (sessionId: string) => {
    setCurrentSessionId(sessionId);
  };

  const handleNewChat = () => {
    const newId = addNewSession(orderedSessions);
    setCurrentSessionId(newId);
    // querySelector because the textarea ref lives inside ChatInput and is not exposed to this parent
    setTimeout(() => {
      const textarea = document.querySelector<HTMLTextAreaElement>(
        '[data-testid="input-wrapper"] textarea',
      );
      textarea?.focus();
    }, FOCUS_DELAY_MS);
  };

  const handleDeleteSession = (sessionId: string) => {
    handleDelete(sessionId);
    removeLocalSession(sessionId);
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
      className="h-full w-full muted shadow-lg flex flex-col relative z-[50] @container/chat-panel"
      onDragOver={dragOver}
      onDragEnter={dragEnter}
      onDragLeave={dragLeave}
      onDrop={onDrop}
    >
      <div className="flex-1 flex overflow-hidden">
        <AnimatedConditional isOpen={sidebarOpen} width={SESSION_SIDEBAR_WIDTH}>
          <div
            style={{ width: SESSION_SIDEBAR_WIDTH }}
            className="h-full overflow-y-auto border-r border-border bg-black/10 dark:bg-black/20"
          >
            <div className="p-4">
              <ChatSidebar
                sessions={orderedSessions}
                onNewChat={handleNewChat}
                onSessionSelect={handleSessionSelect}
                currentSessionId={currentSessionId}
                onDeleteSession={handleDeleteSession}
                onOpenLogs={handleOpenLogs}
                renameLocalSession={renameLocalSession}
              />
            </div>
          </div>
        </AnimatedConditional>
        <div className="flex-1 flex flex-col overflow-hidden pt-2">
          <ChatHeader
            sessions={orderedSessions}
            onNewChat={handleNewChat}
            onSessionSelect={handleSessionSelect}
            currentSessionId={currentSessionId}
            currentFlowId={currentFlowId}
            isFullscreen={isFullscreen}
            onDeleteSession={handleDeleteSession}
            onClose={handleClose}
            openLogsModal={openLogsModal}
            setOpenLogsModal={setOpenLogsModal}
            renameLocalSession={renameLocalSession}
          />
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden playground-messages-wrapper">
            <StickToBottom
              className="flex-1 min-h-0 overflow-hidden"
              resize="smooth"
              initial="instant"
            >
              <StickToBottom.Content className="flex flex-col min-h-full overflow-x-hidden">
                <div
                  style={
                    isFullscreen
                      ? { maxWidth: CHAT_CONTENT_MAX_WIDTH }
                      : undefined
                  }
                  className={cn(
                    "flex flex-col w-full",
                    isFullscreen && "p-0 mx-auto",
                  )}
                >
                  <Messages
                    visibleSession={currentSessionId ?? currentFlowId ?? null}
                    playgroundPage={true}
                  />
                </div>
              </StickToBottom.Content>
            </StickToBottom>

            <div
              className={cn(
                "flex-shrink-0 p-4",
                isFullscreen && "flex justify-center",
              )}
            >
              <div
                style={
                  isFullscreen
                    ? { maxWidth: CHAT_CONTENT_MAX_WIDTH }
                    : undefined
                }
                className="w-full p-0"
              >
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
