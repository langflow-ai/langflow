import {
  useDeleteMessages,
  useGetMessagesQuery,
} from "@/controllers/API/queries/messages";
import { useCallback, useEffect, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { getInputsAndOutputs } from "@/utils/storeUtils";
import { AllNodeType } from "@/types/flow";
import { useMessagesStore } from "src/stores/messageStore";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import BaseModal from "@/modals/baseModal";
import { usePlaygroundStore } from "src/stores/playgroundStore";
import { ChatViewWrapper } from "../chatView/chatViewWrapper";
import { cn } from "src/utils/style";
import { SidebarOpenView } from "../sidebar/sideBarOpen";
import { SelectedViewField } from "../selectedViewField/selectedViewField";

export default function IOModal({
  children,
  disable,
  nodes,
  callbacks,
  mode,
  initialChatValue
}: {
    children: React.ReactNode;
    disable: boolean;
    nodes?: AllNodeType[];
    viewmode: "chat" | "flow";
    callbacks: {
        onDeleteSession: (session_id: string) => void;
        onSessionSelected: (session_id: string) => void;
        onError: (error: string) => void;
        onLockChat: (lock: boolean) => void;
    }
    api:{
    getLockChat: () => boolean;
    setLockChat: (lock: boolean) => void;
    }
    mode: "modal" | "full-screen",
    initialChatValue?: string
}): JSX.Element {
  const { inputs, outputs } = getInputsAndOutputs(nodes ?? []);
  const chatInput = inputs.find(
    (input) => input.type === "ChatInput",
  );
  const chatOutput = outputs.find(
    (output) => output.type === "ChatOutput",
  )
  const haveChat = chatInput || chatOutput;
  const deleteSession = useMessagesStore((state) => state.deleteSession);
  const currentFlowId = usePlaygroundStore((state) => state.currentFlowId);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const { onDeleteSession, onError } = callbacks;

  const { mutate: deleteSessionFunction } = useDeleteMessages();
  const [visibleSession, setvisibleSession] = useState<string | undefined>(
    currentFlowId,
  );


  function handleDeleteSession(session_id: string) {
    deleteSessionFunction(
      {
        ids: messages
          .filter((msg) => msg.session_id === session_id)
          .map((msg) => msg.id),
      },
      {
        onSuccess: () => {
          onDeleteSession(session_id);
            deleteSession(session_id);
            if (visibleSession === session_id) {
              setvisibleSession(undefined);
            }
        },
        onError: () => {
          onError("Error deleting Session.");
        },
      },
    );
  }

  function startView() {
    if (!chatInput && !chatOutput) {
      if (inputs.length > 0) {
        return inputs[0];
      } else {
        return outputs[0];
      }
    } else {
      return undefined;
    }
  }

  const [selectedViewField, setSelectedViewField] = useState<
    { type: string; id: string } | undefined
  >(startView());

  const buildFlow = usePlaygroundStore((state) => state.buildFlow);
  const lockChat = usePlaygroundStore((state) => state.lockChat);
  const setLockChat = usePlaygroundStore((state) => state.setLockChat);
  const messages = useMessagesStore((state) => state.messages);
  const [sessions, setSessions] = useState<string[]>(
    Array.from(
      new Set(
        messages
          .filter((message) => message.flow_id === currentFlowId)
          .map((message) => message.session_id),
      ),
    ),
  );
  const [sessionId, setSessionId] = useState<string>(currentFlowId);
  const { isFetched: messagesFetched } = useGetMessagesQuery(
    {
      mode: "union",
      id: currentFlowId,
    },
    { enabled: true },
  );

  const chatValue = usePlaygroundStore((state) => state.chatValueStore);
  const setChatValue = usePlaygroundStore((state) => state.setChatValueStore);

  const sendMessage = useCallback(
    async ({
      repeat = 1,
      files,
    }: {
      repeat: number;
      files?: string[];
    }): Promise<void> => {
      setLockChat(true);
      setChatValue("");
      for (let i = 0; i < repeat; i++) {
        await buildFlow({
          input_value: chatValue,
          startNodeId: chatInput?.id,
          files: files,
          silent: true,
          session: sessionId,
          setLockChat,
        }).catch((err) => {
          console.error(err);
          setLockChat(false);
        });
      }
      // refetch();
      setLockChat(false);
    },
    [
      setLockChat,
      setChatValue,
      chatValue,
      chatInput?.id,
      sessionId,
      buildFlow,
    ],
  );

  useEffect(() => {
    const sessions = new Set<string>();
    messages
      .filter((message) => message.flow_id === currentFlowId)
      .forEach((row) => {
        sessions.add(row.session_id);
      });
    setSessions((prev) => {
      if (prev.length < Array.from(sessions).length) {
        // set the new session as visible
        setvisibleSession(
          Array.from(sessions)[Array.from(sessions).length - 1],
        );
      }
      return Array.from(sessions);
    });
  }, [messages, currentFlowId]);

  useEffect(() => {
    if (!visibleSession) {
      setSessionId(
        `Session ${new Date().toLocaleString("en-US", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, second: "2-digit", timeZone: "UTC" })}`,
      );
    } else if (visibleSession) {
      setSessionId(visibleSession);
      if (selectedViewField?.type === "Session") {
        setSelectedViewField({
          id: visibleSession,
          type: "Session",
        });
      }
    }
  }, [visibleSession, selectedViewField?.type]);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024) {
        // 1024px is Tailwind's 'lg' breakpoint
        setSidebarOpen(false);
      } else {
        setSidebarOpen(true);
      }
    };

    // Initial check
    handleResize();

    // Add event listener
    window.addEventListener("resize", handleResize);

    // Cleanup
    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  return (
    <BaseModal
      disable={disable}
      type={mode === "full-screen" ? "full-screen" : undefined}
      onSubmit={() => sendMessage({ repeat: 1 })}
      size="x-large"
      className="!rounded-[12px] p-0"
    >
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      {/* TODO ADAPT TO ALL TYPES OF INPUTS AND OUTPUTS */}
      <BaseModal.Content overflowHidden className="h-full">
          <div className="flex-max-width h-full">
            <div
              className={cn(
                "flex h-full flex-shrink-0 flex-col justify-start transition-all duration-300",
                sidebarOpen
                  ? "absolute z-50 lg:relative lg:w-1/5 lg:max-w-[280px]"
                  : "w-0",
              )}
            >
              <div className="flex h-full flex-col overflow-y-auto border-r border-border bg-muted p-4 text-center custom-scroll dark:bg-canvas">
                <div className="flex items-center gap-2 pb-8">
                  <ShadTooltip
                    styleClasses="z-50"
                    side="right"
                    content="Hide sidebar"
                  >
                    <Button
                      variant="ghost"
                      className="flex h-8 w-8 items-center justify-center !p-0"
                      onClick={() => setSidebarOpen(!sidebarOpen)}
                    >
                      <IconComponent
                        name={sidebarOpen ? "PanelLeftClose" : "PanelLeftOpen"}
                        className="h-[18px] w-[18px] text-ring"
                      />
                    </Button>
                  </ShadTooltip>
                  {sidebarOpen && (
                    <div className="font-semibold">Playground</div>
                  )}
                </div>
                {sidebarOpen && (
                  <SidebarOpenView
                    sessions={sessions}
                    setSelectedViewField={setSelectedViewField}
                    setvisibleSession={setvisibleSession}
                    handleDeleteSession={handleDeleteSession}
                    visibleSession={visibleSession}
                    selectedViewField={selectedViewField}
                  />
                )}
              </div>
            </div>
            <div className="flex h-full min-w-96 flex-grow bg-background">
              {selectedViewField && (
                <SelectedViewField
                  selectedViewField={selectedViewField}
                  setSelectedViewField={setSelectedViewField}
                  haveChat={haveChat}
                  inputs={inputs}
                  outputs={outputs}
                  sessions={sessions}
                  currentFlowId={currentFlowId}
                  nodes={nodes ?? []}
                />
              )}
              <ChatViewWrapper
                initialChatValue={initialChatValue}
                selectedViewField={selectedViewField}
                visibleSession={visibleSession}
                sessions={sessions}
                sidebarOpen={sidebarOpen}
                currentFlowId={currentFlowId}
                setSidebarOpen={setSidebarOpen}
                setvisibleSession={setvisibleSession}
                setSelectedViewField={setSelectedViewField}
                haveChat={haveChat}
                messagesFetched={messagesFetched}
                sessionId={sessionId}
                sendMessage={sendMessage}
                lockChat={lockChat}
              />
            </div>
          </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
