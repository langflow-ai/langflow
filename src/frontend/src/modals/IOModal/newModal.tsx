import {
  useDeleteMessages,
  useGetMessagesQuery,
} from "@/controllers/API/queries/messages";
import { useUtilityStore } from "@/stores/utilityStore";
import { useEffect, useState } from "react";
import AccordionComponent from "../../components/accordionComponent";
import IconComponent from "../../components/genericIconComponent";
import ShadTooltip from "../../components/shadTooltipComponent";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { CHAT_FORM_DIALOG_SUBTITLE } from "../../constants/constants";
import { InputOutput } from "../../constants/enums";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { useMessagesStore } from "../../stores/messagesStore";
import { IOModalPropsType } from "../../types/components";
import { NodeType } from "../../types/flow";
import { cn } from "../../utils/utils";
import BaseModal from "../baseModal";
import IOFieldView from "./components/IOFieldView";
import SessionSelector from "./components/IOFieldView/components/sessionSelector/newSessionSelector";
import SessionView from "./components/SessionView";
import ChatView from "./components/chatView/newChatView";

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
  const [chatValue, setChatValue] = useState("");
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const setNode = useFlowStore((state) => state.setNode);
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
  const flowPool = useFlowStore((state) => state.flowPool);
  const [sessionId, setSessionId] = useState<string>(currentFlowId);
  useGetMessagesQuery(
    {
      mode: "union",
      id: currentFlowId,
    },
    { enabled: open },
  );

  async function sendMessage({
    repeat = 1,
    files,
  }: {
    repeat: number;
    files?: string[];
  }): Promise<void> {
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
    if (chatInput) {
      setNode(chatInput.id, (node: NodeType) => {
        const newNode = { ...node };
        if (newNode.data.node?.template) {
          newNode.data.node!.template["input_value"].value = chatValue;
        }
        return newNode;
      });
    }
  }

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
      type={isPlayground ? "modal" : undefined}
      onSubmit={() => sendMessage({ repeat: 1 })}
      size="x-large"
      className="!rounded-[12px] p-0"
    >
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      {/* TODO ADAPT TO ALL TYPES OF INPUTS AND OUTPUTS */}
      <BaseModal.Content overflowHidden>
        <div className="flex-max-width h-full">
          <div
            className={cn(
              "flex h-full flex-shrink-0 flex-col justify-start transition-all duration-300",
              sidebarOpen
                ? "absolute z-50 lg:relative lg:w-1/5 lg:max-w-[280px]"
                : "w-0",
            )}
          >
            <div className="flex h-full flex-col overflow-y-auto border-r border-border bg-muted p-6 text-center custom-scroll dark:bg-background">
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
                {sidebarOpen && <div className="font-semibold">Playground</div>}
              </div>
              {sidebarOpen && (
                <div className="flex flex-col pl-3">
                  <div className="flex flex-col gap-2 pb-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <IconComponent
                          name="MessagesSquare"
                          className="h-[18px] w-[18px] text-ring"
                        />
                        <div className="text-[13px] font-normal">Chat</div>
                      </div>
                      <ShadTooltip styleClasses="z-50" content="New Chat">
                        <div>
                          <Button
                            data-testid="new-chat"
                            variant="ghost"
                            className="flex h-8 w-8 items-center justify-center !p-0"
                            onClick={(_) => {
                              setvisibleSession(undefined);
                              setSelectedViewField(undefined);
                            }}
                          >
                            <IconComponent
                              name="Plus"
                              className="h-[18px] w-[18px] text-ring"
                            />
                          </Button>
                        </div>
                      </ShadTooltip>
                    </div>
                  </div>
                  <div className="flex flex-col">
                    {sessions.map((session, index) => (
                      <SessionSelector
                        setSelectedView={setSelectedViewField}
                        selectedView={selectedViewField}
                        key={index}
                        session={session}
                        deleteSession={(session) => {
                          handleDeleteSession(session);
                          if (selectedViewField?.id === session) {
                            setSelectedViewField(undefined);
                          }
                        }}
                        updateVisibleSession={(session) => {
                          setvisibleSession(session);
                        }}
                        toggleVisibility={() => {
                          setvisibleSession(session);
                        }}
                        isVisible={visibleSession === session}
                        inspectSession={(session) => {
                          setSelectedViewField({
                            id: session,
                            type: "Session",
                          });
                        }}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
          <div className="flex h-full min-w-96 flex-grow bg-background dark:bg-accent">
            {selectedViewField && (
              <div
                className={cn(
                  "flex h-full w-full flex-col items-start gap-4 p-4",
                  !selectedViewField ? "hidden" : "",
                )}
              >
                <div className="font-xl flex items-center justify-center gap-3 font-semibold">
                  {haveChat && (
                    <button onClick={() => setSelectedViewField(undefined)}>
                      <IconComponent
                        name={"ArrowLeft"}
                        className="h-6 w-6"
                      ></IconComponent>
                    </button>
                  )}
                  {
                    nodes.find((node) => node.id === selectedViewField.id)?.data
                      .node.display_name
                  }
                </div>
                <div className="h-full w-full">
                  {inputs.some(
                    (input) => input.id === selectedViewField.id,
                  ) && (
                    <IOFieldView
                      type={InputOutput.INPUT}
                      left={false}
                      fieldType={selectedViewField.type!}
                      fieldId={selectedViewField.id!}
                    />
                  )}
                  {outputs.some(
                    (output) => output.id === selectedViewField.id,
                  ) && (
                    <IOFieldView
                      type={InputOutput.OUTPUT}
                      left={false}
                      fieldType={selectedViewField.type!}
                      fieldId={selectedViewField.id!}
                    />
                  )}
                  {sessions.some(
                    (session) => session === selectedViewField.id,
                  ) && (
                    <SessionView
                      session={selectedViewField.id}
                      id={currentFlowId}
                    />
                  )}
                </div>
              </div>
            )}
            <div
              className={cn(
                "flex h-full w-full flex-col justify-between p-6",
                selectedViewField ? "hidden" : "",
              )}
            >
              <div className="mb-4 h-[5%] text-[16px] font-semibold">
                {visibleSession && sessions.length > 0 && sidebarOpen && (
                  <div className="hidden lg:block">
                    {visibleSession === currentFlowId
                      ? "Default Session"
                      : `${visibleSession}`}
                  </div>
                )}
                <div className={cn(sidebarOpen ? "lg:hidden" : "")}>
                  <div className="-ml-4 -mt-4 flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setSidebarOpen(true)}
                      className="h-8 w-8"
                    >
                      <IconComponent
                        name={"PanelLeftOpen"}
                        className="h-[18px] w-[18px] text-ring"
                      />
                    </Button>
                    <div className="font-semibold">Playground</div>
                  </div>
                </div>
                <div
                  className={cn(
                    sidebarOpen ? "pointer-events-none opacity-0" : "",
                    "absolute right-10 top-2 flex h-8 w-8 items-center justify-center rounded-sm ring-offset-background transition-opacity focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
                  )}
                >
                  <ShadTooltip styleClasses="z-50" content="New Chat">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(_) => {
                        setvisibleSession(undefined);
                        setSelectedViewField(undefined);
                      }}
                    >
                      <IconComponent
                        name="Plus"
                        className="h-[18px] w-[18px] text-ring"
                      />
                    </Button>
                  </ShadTooltip>
                </div>
              </div>
              {haveChat ? (
                <div
                  className={cn(
                    visibleSession ? "h-[95%]" : "h-full",
                    sidebarOpen
                      ? "pointer-events-none blur-sm lg:pointer-events-auto lg:blur-0"
                      : "",
                  )}
                >
                  <ChatView
                    focusChat={sessionId}
                    sendMessage={sendMessage}
                    chatValue={chatValue}
                    setChatValue={setChatValue}
                    lockChat={lockChat}
                    setLockChat={setLockChat}
                    visibleSession={visibleSession}
                    closeChat={
                      !canvasOpen
                        ? undefined
                        : () => {
                            setOpen(false);
                          }
                    }
                  />
                </div>
              ) : (
                <span className="flex h-full w-full items-center justify-center font-thin text-muted-foreground">
                  Select an IO component to view
                </span>
              )}
            </div>
          </div>
        </div>
      </BaseModal.Content>
      {!haveChat ? (
        <BaseModal.Footer
          submit={{
            label: "Run Flow",
            icon: (
              <IconComponent
                name={isBuilding ? "Loader2" : "Zap"}
                className={cn(
                  "h-4 w-4",
                  isBuilding
                    ? "animate-spin"
                    : "fill-current text-medium-indigo",
                )}
              />
            ),
          }}
        />
      ) : (
        <></>
      )}
    </BaseModal>
  );
}
