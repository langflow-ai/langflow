import { useEffect, useMemo, useState } from "react";
import { StickToBottom } from "use-stick-to-bottom";
import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import LangflowLogoColor from "@/assets/LangflowLogoColor.svg?react";
import ThemeButtons from "@/components/core/appHeaderComponent/components/ThemeButtons";
import { ChatHeader } from "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-header";
import { ChatSidebar } from "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-sidebar";
import { useEditSessionInfo } from "@/components/core/playgroundComponent/chat-view/chat-header/hooks/use-edit-session-info";
import { useGetAddSessions } from "@/components/core/playgroundComponent/chat-view/chat-header/hooks/use-get-add-sessions";
import { ChatInput } from "@/components/core/playgroundComponent/chat-view/chat-input";
import useDragAndDrop from "@/components/core/playgroundComponent/chat-view/chat-input/hooks/use-drag-and-drop";
import { Messages } from "@/components/core/playgroundComponent/chat-view/chat-messages";
import { useChatHistory } from "@/components/core/playgroundComponent/chat-view/chat-messages/hooks/use-chat-history";
import { useSendMessage } from "@/components/core/playgroundComponent/chat-view/hooks/use-send-message";
import { useGetFlowId } from "@/components/core/playgroundComponent/hooks/use-get-flow-id";
import { AnimatedConditional } from "@/components/ui/animated-close";
import { Button } from "@/components/ui/button";
import { TextEffectPerChar } from "@/components/ui/textAnimation";
import { ENABLE_PUBLISH } from "@/customization/feature-flags";
import { customOpenNewTab } from "@/customization/utils/custom-open-new-tab";
import { LangflowButtonRedirectTarget } from "@/customization/utils/urls";
import { track } from "@/customization/utils/analytics";
import useFlowStore from "@/stores/flowStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { FilePreviewType } from "@/types/components";

export function ShareablePlaygroundContent() {
  const currentFlowId = useGetFlowId();
  const inputs = useFlowStore((state) => state.inputs);
  const nodes = useFlowStore((state) => state.nodes);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const setChatValueStore = useUtilityStore((state) => state.setChatValueStore);

  const [currentSessionId, setCurrentSessionId] = useState<string | undefined>(
    currentFlowId,
  );
  const [openLogsModal, setOpenLogsModal] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [files, setFiles] = useState<FilePreviewType[]>([]);
  const [isDragging, setIsDragging] = useState(false);

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
    push(currentFlowId);
    sessions.forEach(push);
    return ordered;
  }, [sessions, currentFlowId]);

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
    const handleResize = () => {
      if (window.innerWidth < 1024) {
        setSidebarOpen(false);
      } else {
        setSidebarOpen(true);
      }
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const handleSessionSelect = (sessionId: string) => {
    setCurrentSessionId(sessionId);
  };

  const handleNewChat = () => {
    const newId = addNewSession(orderedSessions);
    setCurrentSessionId(newId);
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

  const handleLangflowButtonClick = () => {
    track("LangflowButtonClick");
    customOpenNewTab(LangflowButtonRedirectTarget());
  };

  return (
    <div
      className="h-full w-full flex flex-col relative"
      onDragOver={dragOver}
      onDragEnter={dragEnter}
      onDragLeave={dragLeave}
      onDrop={onDrop}
    >
      <div className="flex-1 flex overflow-hidden">
        <AnimatedConditional isOpen={sidebarOpen} width="218px">
          <div className="h-full overflow-y-auto border-r border-border w-218 flex flex-col">
            <div className="flex-1 p-4">
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
            {ENABLE_PUBLISH && (
              <div className="flex w-full flex-col gap-8 border-t border-border px-2 py-4">
                <div className="flex items-center justify-between px-2">
                  <div className="text-sm">Theme</div>
                  <ThemeButtons />
                </div>
                <Button
                  onClick={handleLangflowButtonClick}
                  variant="primary"
                  className="w-full !rounded-xl shadow-lg"
                >
                  <LangflowLogoColor />
                  <div className="text-sm">Built with Langflow</div>
                </Button>
              </div>
            )}
          </div>
        </AnimatedConditional>
        <div className="flex-1 flex flex-col overflow-hidden pt-2">
          <ChatHeader
            sessions={orderedSessions}
            onNewChat={handleNewChat}
            onSessionSelect={handleSessionSelect}
            currentSessionId={currentSessionId}
            currentFlowId={currentFlowId}
            isFullscreen={true}
            onDeleteSession={handleDeleteSession}
            openLogsModal={openLogsModal}
            setOpenLogsModal={setOpenLogsModal}
            renameLocalSession={renameLocalSession}
          />
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            <StickToBottom
              className="flex-1 min-h-0 overflow-hidden"
              resize="smooth"
              initial="instant"
            >
              <StickToBottom.Content className="flex flex-col min-h-full overflow-x-hidden">
                <div className="flex flex-col w-full max-w-[744px] p-0 mx-auto">
                  {chatHistory.length === 0 && !isBuilding ? (
                    <div className="flex flex-grow w-full flex-col items-center justify-center">
                      <div className="flex flex-col items-center justify-center gap-4 p-8">
                        <LangflowLogo
                          title="Langflow logo"
                          className="h-10 w-10 scale-[1.5]"
                        />
                        <div className="flex flex-col items-center justify-center">
                          <h3 className="mt-2 pb-2 text-2xl font-semibold text-primary">
                            New chat
                          </h3>
                          <p
                            className="text-lg text-muted-foreground"
                            data-testid="new-chat-text"
                          >
                            <TextEffectPerChar>
                              Test your flow with a chat prompt
                            </TextEffectPerChar>
                          </p>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <Messages
                      visibleSession={
                        currentSessionId ?? currentFlowId ?? null
                      }
                      playgroundPage={true}
                    />
                  )}
                </div>
              </StickToBottom.Content>
            </StickToBottom>

            <div className="flex-shrink-0 p-4 flex justify-center">
              <div className="w-full max-w-[744px] p-0">
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
