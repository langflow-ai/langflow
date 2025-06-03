//import LangflowLogoColor from "@/assets/LangflowLogocolor.svg?react";
import ThemeButtons from "@/components/core/appHeaderComponent/components/ThemeButtons";
import { EventDeliveryType } from "@/constants/enums";
import { useGetConfig } from "@/controllers/API/queries/config/use-get-config";
import {
  useDeleteMessages,
  useGetMessagesQuery,
} from "@/controllers/API/queries/messages";
import { ENABLE_PUBLISH } from "@/customization/feature-flags";
import { track } from "@/customization/utils/analytics";
import { customOpenNewTab } from "@/customization/utils/custom-open-new-tab";
import { LangflowButtonRedirectTarget } from "@/customization/utils/urls";
import { useUtilityStore } from "@/stores/utilityStore";
import { swatchColors } from "@/utils/styleUtils";
import { useCallback, useEffect, useState } from "react";
import { v5 as uuidv5 } from "uuid";
import { useShallow } from "zustand/react/shallow";
import LangflowLogoColor from "../../assets/LangflowLogoColor.svg?react";
import IconComponent from "../../components/common/genericIconComponent";
import ShadTooltip from "../../components/common/shadTooltipComponent";
import { Button } from "../../components/ui/button";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { useMessagesStore } from "../../stores/messagesStore";
import { IOModalPropsType } from "../../types/components";
import { cn, getNumberFromString } from "../../utils/utils";
import BaseModal from "../baseModal";
import { ChatViewWrapper } from "./components/chat-view-wrapper";
import { SelectedViewField } from "./components/selected-view-field";
import { SidebarOpenView } from "./components/sidebar-open-view";

export default function IOModal({
  children,
  open,
  setOpen,
  disable,
  isPlayground,
  canvasOpen,
  playgroundPage,
}: IOModalPropsType): JSX.Element {
  const setIOModalOpen = useFlowsManagerStore((state) => state.setIOModalOpen);
  const inputs = useFlowStore((state) => state.inputs);
  const outputs = useFlowStore((state) => state.outputs);
  const nodes = useFlowStore((state) => state.nodes);
  const buildFlow = useFlowStore((state) => state.buildFlow);
  const setIsBuilding = useFlowStore((state) => state.setIsBuilding);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const { flowIcon, flowId, flowGradient, flowName } = useFlowStore(
    useShallow((state) => ({
      flowIcon: state.currentFlow?.icon,
      flowId: state.currentFlow?.id,
      flowGradient: state.currentFlow?.gradient,
      flowName: state.currentFlow?.name,
    })),
  );
  const filteredInputs = inputs.filter((input) => input.type !== "ChatInput");
  const chatInput = inputs.find((input) => input.type === "ChatInput");
  const filteredOutputs = outputs.filter(
    (output) => output.type !== "ChatOutput",
  );
  const chatOutput = outputs.find((output) => output.type === "ChatOutput");
  const filteredNodes = nodes.filter(
    (node) =>
      inputs.some((input) => input.id === node.id) ||
      filteredOutputs.some((output) => output.id === node.id),
  );
  const haveChat = chatInput || chatOutput;
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const deleteSession = useMessagesStore((state) => state.deleteSession);
  const clientId = useUtilityStore((state) => state.clientId);
  let realFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const currentFlowId = playgroundPage
    ? uuidv5(`${clientId}_${realFlowId}`, uuidv5.DNS)
    : realFlowId;
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [selectedTab, setSelectedTab] = useState(1);

  const { mutate: deleteSessionFunction } = useDeleteMessages();
  const [visibleSession, setvisibleSession] = useState<string | undefined>(
    currentFlowId,
  );
  const PlaygroundTitle = playgroundPage && flowName ? flowName : "Playground";

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
      if (filteredInputs.length > 0) {
        return filteredInputs[0];
      } else {
        return filteredOutputs[0];
      }
    } else {
      return undefined;
    }
  }

  const [selectedViewField, setSelectedViewField] = useState<
    { type: string; id: string } | undefined
  >(startView());

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
  const setCurrentSessionId = useUtilityStore(
    (state) => state.setCurrentSessionId,
  );

  const { isFetched: messagesFetched } = useGetMessagesQuery(
    {
      mode: "union",
      id: currentFlowId,
    },
    { enabled: open },
  );

  const chatValue = useUtilityStore((state) => state.chatValueStore);
  const setChatValue = useUtilityStore((state) => state.setChatValueStore);
  const eventDeliveryConfig = useUtilityStore((state) => state.eventDelivery);

  const sendMessage = useCallback(
    async ({
      repeat = 1,
      files,
    }: {
      repeat: number;
      files?: string[];
    }): Promise<void> => {
      if (isBuilding) return;
      setChatValue("");
      for (let i = 0; i < repeat; i++) {
        await buildFlow({
          input_value: chatValue,
          startNodeId: chatInput?.id,
          files: files,
          silent: true,
          session: sessionId,
          eventDelivery: eventDeliveryConfig,
        }).catch((err) => {
          console.error(err);
        });
      }
    },
    [
      isBuilding,
      setIsBuilding,
      chatValue,
      chatInput?.id,
      sessionId,
      buildFlow,
      eventDeliveryConfig,
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
    if (Array.from(sessions).length === 0) {
      // If there are no sessions, set the current session to the current flow id
      setSessionId(currentFlowId);
      setCurrentSessionId(currentFlowId);
    } else if (!visibleSession) {
      // Set the current session to the last session if no session is visible
      setSessionId(Array.from(sessions)[Array.from(sessions).length - 1]);
      setCurrentSessionId(
        Array.from(sessions)[Array.from(sessions).length - 1],
      );
    } else {
      // Set the current session to the visible session
      setSessionId(visibleSession);
      setCurrentSessionId(visibleSession);
    }
  }, [messages, currentFlowId, visibleSession, setCurrentSessionId]);

  const { data: config } = useGetConfig();

  useEffect(() => {
    const handleElement = document.getElementById("sized-box");
    const containerElement = document.getElementById("container-sized-box");

    if (handleElement && containerElement) {
      let startX: number, startWidth: number;

      const onMouseMove = (e: MouseEvent) => {
        const dx = e.clientX - startX;
        const newWidth = Math.min(
          Math.max(200, startWidth + dx), // Min width
          containerElement.offsetWidth - 200, // Max width based on container
        );
        handleElement.style.width = `${newWidth}px`;
      };

      const onMouseUp = () => {
        document.removeEventListener("mousemove", onMouseMove);
        document.removeEventListener("mouseup", onMouseUp);
      };

      const onMouseDown = (e: MouseEvent) => {
        startX = e.clientX;
        startWidth = handleElement.offsetWidth;
        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", onMouseUp);
      };

      handleElement.addEventListener("mousedown", onMouseDown);

      return () => {
        handleElement.removeEventListener("mousedown", onMouseDown);
      };
    }
  }, []);

  const LangflowButtonClick = () => {
    track("LangflowButtonClick");
    customOpenNewTab(LangflowButtonRedirectTarget());
  };

  useEffect(() => {
    if (playgroundPage && messages.length > 0) {
      window.sessionStorage.setItem(currentFlowId, JSON.stringify(messages));
    }
  }, [playgroundPage, messages, currentFlowId]);

  const swatchIndex =
    (flowGradient && !isNaN(parseInt(flowGradient))
      ? parseInt(flowGradient)
      : getNumberFromString(flowGradient ?? flowId ?? "")) %
    swatchColors.length;

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      className={cn(
        "h-[80vh] w-[80vw] dark:bg-muted-foreground dark:text-primary-foreground",
      )}
      disable={disable}
    >
      <BaseModal.Header>
        <div
          className={cn("w-full", "justify-between", "flex items-start gap-3")}
        >
          <div className="flex">
            {isPlayground && !playgroundPage && (
              <ShadTooltip content="Langflow">
                <Button
                  className="!p-0"
                  variant="ghost"
                  onClick={LangflowButtonClick}
                >
                  <LangflowLogoColor className="h-6 w-6" />
                </Button>
              </ShadTooltip>
            )}
            {isPlayground && playgroundPage && (
              <ShadTooltip content={PlaygroundTitle}>
                <IconComponent
                  name="Variable"
                  className="h-6 w-6 text-primary"
                />
              </ShadTooltip>
            )}

            {!isPlayground && (
              <ShadTooltip content={flowName}>
                <IconComponent
                  name="FileText"
                  className="h-6 w-6 text-primary"
                />
              </ShadTooltip>
            )}
            <span className="pl-2 pt-1" data-testid="modal-title">
              {isPlayground ? PlaygroundTitle : flowName}
            </span>
            <span className="pl-2 pt-1 font-normal text-muted-foreground">
              {currentFlowId?.slice(0, 4) + "..." + currentFlowId?.slice(-4)}
            </span>
          </div>
          <div className="ml-auto mr-1 flex">
            {isPlayground && ENABLE_PUBLISH && (
              <ShadTooltip content="Publish Flow">
                <Button
                  className="group"
                  variant="ghost"
                  size="icon"
                  onClick={() => {
                    // TODO: add publish logic
                  }}
                >
                  <IconComponent
                    name="Share2"
                    className="h-5 w-5 text-primary"
                  />
                </Button>
              </ShadTooltip>
            )}
            <ShadTooltip content="Refresh">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  setSelectedTab(1);
                  if (chatInput || chatOutput) {
                    setvisibleSession(currentFlowId);
                  }
                }}
              >
                <IconComponent
                  name="RefreshCw"
                  className="h-5 w-5 text-primary"
                />
              </Button>
            </ShadTooltip>

            <ShadTooltip content="Delete Session">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  handleDeleteSession(sessionId);
                }}
              >
                <IconComponent name="Trash2" className="h-5 w-5 text-primary" />
              </Button>
            </ShadTooltip>

            <ShadTooltip content="Exit">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setOpen(false)}
              >
                <IconComponent name="X" className="h-5 w-5 text-primary" />
              </Button>
            </ShadTooltip>
          </div>
        </div>
      </BaseModal.Header>
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      {/* TODO ADAPT TO ALL TYPES OF INPUTS AND OUTPUTS */}
      <BaseModal.Content overflowHidden className="h-full">
        {open && (
          <div className="flex-max-width h-full">
            <div
              className={cn(
                "flex h-full flex-shrink-0 flex-col justify-start overflow-hidden transition-all duration-300",
                sidebarOpen
                  ? "absolute z-50 lg:relative lg:w-1/5 lg:max-w-[280px]"
                  : "w-0",
              )}
            >
              <div
                className={cn(
                  "relative flex h-full flex-col overflow-y-auto border-r border-border bg-muted p-4 text-center custom-scroll dark:bg-canvas",
                  playgroundPage ? "pt-[15px]" : "pt-3.5",
                )}
              >
                <div className="flex items-center justify-between gap-2 pb-8 align-middle">
                  <div className="flex items-center gap-2">
                    <div
                      className={cn(
                        `flex rounded p-1`,
                        swatchColors[swatchIndex],
                      )}
                    >
                      <IconComponent
                        name={flowIcon ?? "Workflow"}
                        className="h-3.5 w-3.5"
                      />
                    </div>
                    {sidebarOpen && (
                      <div className="truncate font-semibold">
                        {PlaygroundTitle}
                      </div>
                    )}
                  </div>
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
                </div>
                {sidebarOpen && (
                  <SidebarOpenView
                    sessions={sessions}
                    setSelectedViewField={setSelectedViewField}
                    setvisibleSession={setvisibleSession}
                    handleDeleteSession={handleDeleteSession}
                    visibleSession={visibleSession}
                    selectedViewField={selectedViewField}
                    playgroundPage={!!playgroundPage}
                  />
                )}
              </div>
            </div>
            <div
              id="container-sized-box"
              className={
                "relative flex h-full w-full flex-col lg:flex-row lg:overflow-hidden"
              }
            >
              {selectedViewField ? (
                <SelectedViewField
                  selectedViewField={selectedViewField}
                  setSelectedViewField={setSelectedViewField}
                  open={open}
                  closeModal={() => setOpen(false)}
                  chatOutput={chatOutput}
                  chatInput={chatInput}
                  messages={messages}
                  messagesFetched={messagesFetched}
                  sessionId={sessionId}
                  setSessionId={setSessionId}
                  sendMessage={sendMessage}
                  disabled={isBuilding || disable}
                  setChatValue={setChatValue}
                  chatValue={chatValue}
                  isPlayground={isPlayground}
                  currentFlowId={currentFlowId}
                  nodes={filteredNodes}
                />
              ) : (
                <ChatViewWrapper
                  sendMessage={sendMessage}
                  chatOutput={chatOutput}
                  chatInput={chatInput}
                  messages={messages}
                  messagesFetched={messagesFetched}
                  sessionId={sessionId}
                  setSessionId={setSessionId}
                  disabled={isBuilding || disable}
                  setChatValue={setChatValue}
                  chatValue={chatValue}
                  open={open}
                  isPlayground={isPlayground}
                  currentFlowId={currentFlowId}
                  playgroundTitle={PlaygroundTitle}
                />
              )}
            </div>
          </div>
        )}
      </BaseModal.Content>
      <BaseModal.Footer>
        <div className="flex w-full justify-between">
          <div className="flex items-center gap-2">
            {isPlayground && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  handleResize();
                }}
              >
                <IconComponent
                  name="PanelLeft"
                  className={cn(
                    "h-4 w-4 fill-foreground text-foreground opacity-50 hover:opacity-100",
                    sidebarOpen ? "rotate-180" : "rotate-0",
                  )}
                />
              </Button>
            )}
            <span className="text-sm font-normal text-muted-foreground">
              {config?.frontend_timeout ? `v${config?.frontend_timeout}` : ""}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <ThemeButtons />
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  track("Langflow Button Clicked");
                  window.open(LangflowButtonRedirectTarget(), "_blank");
                }}
              >
                <LangflowLogoColor className="h-6 w-6" />
              </Button>
            </div>
          </div>
        </div>
      </BaseModal.Footer>
    </BaseModal>
  );
}
