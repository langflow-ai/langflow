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
import { LangflowButtonRedirectTarget } from "@/customization/utils/urls";
import { useUtilityStore } from "@/stores/utilityStore";
import { swatchColors } from "@/utils/styleUtils";
import { useCallback, useEffect, useState } from "react";
import { v5 as uuidv5 } from "uuid";
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
  const clientId = useUtilityStore((state) => state.clientId);
  let realFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const currentFlowId = playgroundPage
    ? uuidv5(`${clientId}_${realFlowId}`, uuidv5.DNS)
    : realFlowId;
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const { mutate: deleteSessionFunction } = useDeleteMessages();
  const [visibleSession, setvisibleSession] = useState<string | undefined>(
    currentFlowId,
  );
  const flowName = useFlowStore((state) => state.currentFlow?.name);
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
    [isBuilding, setIsBuilding, chatValue, chatInput?.id, sessionId, buildFlow],
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
  }, [messages, currentFlowId, visibleSession]);

  const { data: config } = useGetConfig();

  const handleResize = useCallback(() => {
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

      handleElement.addEventListener("mousedown", (e: MouseEvent) => {
        startX = e.clientX;
        startWidth = handleElement.offsetWidth;
        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", onMouseUp);
      });
    }
  }, []);

  useEffect(() => {
    handleResize();
  }, [handleResize]);

  const LangflowButtonClick = () => {
    track("Langflow Button Clicked");
    window.open(LangflowButtonRedirectTarget(), "_blank");
  };

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      className={
        "h-[80vh] w-[80vw] dark:bg-muted-foreground dark:text-primary-foreground"
      }
      disable={disable}
    >
      <BaseModal.Header className={cn("w-full", "justify-between")}>
        <div className="flex w-full items-start gap-3">
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
              <ShadTooltip content={currentFlow?.name}>
                <IconComponent
                  name="FileText"
                  className="h-6 w-6 text-primary"
                />
              </ShadTooltip>
            )}
            <span className="pl-2 pt-1" data-testid="modal-title">
              {isPlayground ? PlaygroundTitle : currentFlow?.name}
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
      <BaseModal.Content>
        <div className="flex h-full w-full">
          <div
            id="sized-box"
            className={cn("relative flex h-full", sidebarOpen ? "w-56" : "w-0")}
          >
            <SidebarOpenView
              playgroundPage={!!playgroundPage}
              currentFlowId={currentFlowId}
              setSelectedTab={setSelectedTab}
              selectedTab={selectedTab}
              sessions={sessions}
              handleDeleteSession={handleDeleteSession}
              sessionId={sessionId}
              setSessionId={setSessionId}
              visibleSession={visibleSession}
            />
            <div className="flex w-full items-center justify-center">
              <div
                className="absolute right-0 top-1/2 z-10 flex h-full cursor-e-resize items-center bg-transparent p-2"
                onMouseDown={(e) => {
                  handleResize();
                }}
              >
                <IconComponent
                  name="ChevronsLeft"
                  className={
                    "h-4 w-4 fill-foreground text-foreground opacity-50 hover:opacity-100"
                  }
                  onClick={() => setSidebarOpen(!sidebarOpen)}
                />
              </div>
            </div>
          </div>
          <div className="flex w-full flex-col" id="container-sized-box">
            <div className="flex h-full flex-col">
              {haveChat ? (
                <ChatViewWrapper
                  sendMessage={sendMessage}
                  chatInput={chatInput}
                  chatOutput={chatOutput}
                  playgroundPage={!!playgroundPage}
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
                  canvasOpen={canvasOpen}
                  setOpen={setOpen}
                  playgroundTitle={PlaygroundTitle}
                />
              ) : (
                // If no chat, render IOFieldView
                <SelectedViewField
                  selectedViewField={selectedViewField}
                  setSelectedViewField={setSelectedViewField}
                  nodes={nodes}
                  haveChat={haveChat}
                  inputs={inputs}
                  outputs={outputs}
                  sessions={sessions}
                  currentFlowId={currentFlowId}
                />
              )}
            </div>
            <BaseModal.Footer>
              {isBuilding || !config?.open_ai_key ? (
                <div className="flex w-full items-center justify-between">
                  <div className="flex w-full flex-row">
                    <span className="ml-auto flex shrink-0 justify-end text-sm text-muted-foreground">
                      {isBuilding && currentFlow?.name === "New Flow"
                        ? "New Flow"
                        : isBuilding
                          ? "Building Flow"
                          : "Ready"}
                      {isBuilding && (
                        <IconComponent
                          name="Loader2"
                          className="ml-2 h-4 w-4 animate-spin"
                        />
                      )}
                    </span>
                    {config?.open_ai_key ? (
                      <div className="w-full flex-row text-right text-sm text-muted-foreground">
                        <span className="text-loading-gradient animate-pulse">
                          Type some text to start the flow
                        </span>
                      </div>
                    ) : (
                      <div className="w-full flex-row text-right text-sm text-muted-foreground">
                        <span>
                          <a
                            className="underline"
                            href="/settings"
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            Set your OpenAI Key
                          </a>
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex w-full items-end justify-between">
                  <ThemeButtons />
                  <span className="ml-auto flex shrink-0 justify-end text-sm text-muted-foreground">
                    Ready
                  </span>
                </div>
              )}
            </BaseModal.Footer>
          </div>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
