import { Separator } from "@/components/ui/separator";
import {
  useDeleteMessages,
  useGetMessagesQuery,
} from "@/controllers/API/queries/messages";
import { useUtilityStore } from "@/stores/utilityStore";
import { useCallback, useEffect, useState } from "react";
import IconComponent from "../../components/common/genericIconComponent";
import ShadTooltip from "../../components/common/shadTooltipComponent";
import { Button } from "../../components/ui/button";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { useMessagesStore } from "../../stores/messagesStore";
import { IOModalPropsType } from "../../types/components";
import { cn } from "../../utils/utils";
import BaseModal from "../baseModal";
import { ChatViewWrapper } from "./components/chat-view-wrapper";
import ChatView from "./components/chatView/chat-view";
import { SelectedViewField } from "./components/selected-view-field";
import { SidebarOpenView } from "./components/sidebar-open-view";

export default function IOModal({
  children,
  open,
  setOpen,
  disable,
  isPlayground,
  canvasOpen,
}: IOModalPropsType): JSX.Element {
  const allNodes = useFlowStore((state) => state.nodes);
  const setIOModalOpen = useFlowsManagerStore((state) => state.setIOModalOpen);
  const inputs = useFlowStore((state) => state.inputs).filter(
    (input) => input.type !== "ChatInput",
  );
  const chatInput = useFlowStore((state) => state.inputs).find(
    (input) => input.type === "ChatInput",
  );
  const outputs = useFlowStore((state) => state.outputs).filter(
    (output) => output.type !== "ChatOutput",
  );
  const chatOutput = useFlowStore((state) => state.outputs).find(
    (output) => output.type === "ChatOutput",
  );
  const nodes = useFlowStore((state) => state.nodes).filter(
    (node) =>
      inputs.some((input) => input.id === node.id) ||
      outputs.some((output) => output.id === node.id),
  );
  const haveChat = chatInput || chatOutput;
  const [selectedTab, setSelectedTab] = useState(
    inputs.length > 0 ? 1 : outputs.length > 0 ? 2 : 0,
  );
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const deleteSession = useMessagesStore((state) => state.deleteSession);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const { mutate: deleteSessionFunction } = useDeleteMessages();
  const [visibleSession, setvisibleSession] = useState<string | undefined>(
    currentFlowId,
  );

  useEffect(() => {
    setIOModalOpen(open);
    return () => {
      setIOModalOpen(false);
    };
  }, [open]);

  function handleDeleteSession(session_id: string) {
    deleteSessionFunction(
      {
        ids: messages
          .filter((msg) => msg.session_id === session_id)
          .map((msg) => msg.id),
      },
      {
        onSuccess: () => {
          setSuccessData({
            title: "Session deleted successfully.",
          });
          deleteSession(session_id);
          if (visibleSession === session_id) {
            setvisibleSession(undefined);
          }
        },
        onError: () => {
          setErrorData({
            title: "Error deleting Session.",
          });
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

  const buildFlow = useFlowStore((state) => state.buildFlow);
  const setIsBuilding = useFlowStore((state) => state.setIsBuilding);
  const lockChat = useFlowStore((state) => state.lockChat);
  const setLockChat = useFlowStore((state) => state.setLockChat);
  const isBuilding = useFlowStore((state) => state.isBuilding);
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
    { enabled: open },
  );

  const chatValue = useUtilityStore((state) => state.chatValueStore);
  const setChatValue = useUtilityStore((state) => state.setChatValueStore);

  const sendMessage = useCallback(
    async ({
      repeat = 1,
      files,
    }: {
      repeat: number;
      files?: string[];
    }): Promise<void> => {
      if (isBuilding) return;
      setIsBuilding(true);
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
      isBuilding,
      setIsBuilding,
      setLockChat,
      chatValue,
      chatInput?.id,
      sessionId,
      buildFlow,
    ],
  );

  useEffect(() => {
    setSelectedTab(inputs.length > 0 ? 1 : outputs.length > 0 ? 2 : 0);
  }, [allNodes.length]);

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
  }, [messages]);

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
  }, [visibleSession]);

  const setPlaygroundScrollBehaves = useUtilityStore(
    (state) => state.setPlaygroundScrollBehaves,
  );

  useEffect(() => {
    if (open) {
      setPlaygroundScrollBehaves("instant");
    }
  }, [open]);

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
      open={open}
      setOpen={setOpen}
      disable={disable}
      type={isPlayground ? "full-screen" : undefined}
      onSubmit={() => sendMessage({ repeat: 1 })}
      size="x-large"
      className="!rounded-[12px] p-0"
    >
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      {/* TODO ADAPT TO ALL TYPES OF INPUTS AND OUTPUTS */}
      <BaseModal.Content overflowHidden className="h-full">
        {open && (
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
                  nodes={nodes}
                />
              )}
              <ChatViewWrapper
                selectedViewField={selectedViewField}
                visibleSession={visibleSession}
                sessions={sessions}
                sidebarOpen={sidebarOpen}
                currentFlowId={currentFlowId}
                setSidebarOpen={setSidebarOpen}
                isPlayground={isPlayground}
                setvisibleSession={setvisibleSession}
                setSelectedViewField={setSelectedViewField}
                haveChat={haveChat}
                messagesFetched={messagesFetched}
                sessionId={sessionId}
                sendMessage={sendMessage}
                lockChat={lockChat}
                setLockChat={setLockChat}
                canvasOpen={canvasOpen}
                setOpen={setOpen}
              />
            </div>
          </div>
        )}
      </BaseModal.Content>
    </BaseModal>
  );
}
