//import LangflowLogoColor from "@/assets/LangflowLogocolor.svg?react";
import ThemeButtons from "@/components/core/appHeaderComponent/components/ThemeButtons";
import {
  useDeleteMessages,
  useGetMessagesQuery,
} from "@/controllers/API/queries/messages";
import { useDeleteSession } from "@/controllers/API/queries/messages/use-delete-sessions";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { ENABLE_PUBLISH } from "@/customization/feature-flags";
import { track } from "@/customization/utils/analytics";
import { customOpenNewTab } from "@/customization/utils/custom-open-new-tab";
import { LangflowButtonRedirectTarget } from "@/customization/utils/urls";
import { useUtilityStore } from "@/stores/utilityStore";
import { swatchColors } from "@/utils/styleUtils";
import { useCallback, useEffect, useRef, useState } from "react";
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
import type { IOModalPropsType } from "../../types/components";
import { cn, getNumberFromString } from "../../utils/utils";
import BaseModal from "../baseModal";
import { ChatViewWrapper } from "./components/chat-view-wrapper";
import { createNewSessionName } from "./components/chatView/chatInput/components/voice-assistant/helpers/create-new-session-name";
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
  const newChatOnPlayground = useFlowStore(
    (state) => state.newChatOnPlayground,
  );
  const setNewChatOnPlayground = useFlowStore(
    (state) => state.setNewChatOnPlayground,
  );

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
  const realFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const currentFlowId = playgroundPage
    ? uuidv5(`${clientId}_${realFlowId}`, uuidv5.DNS)
    : realFlowId;
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const { mutate: deleteSessionFunction } = useDeleteSession();

  const [visibleSession, setvisibleSession] = useState<string | undefined>(
    currentFlowId,
  );
  const PlaygroundTitle = playgroundPage && flowName ? flowName : "Playground";

  const {
    data: sessionsFromDb,
    isLoading: sessionsLoading,
    refetch: refetchSessions,
  } = useGetSessionsFromFlowQuery(
    {
      id: currentFlowId,
    },
    { enabled: open },
  );

  useEffect(() => {
    if (sessionsFromDb && !sessionsLoading) {
      const sessions = [...sessionsFromDb.sessions];
      // Always include the currentFlowId as the default session if it's not already present
      if (!sessions.includes(currentFlowId)) {
        sessions.unshift(currentFlowId);
      }
      setSessions(sessions);
    }
  }, [sessionsFromDb, sessionsLoading, currentFlowId]);

  useEffect(() => {
    setIOModalOpen(open);
    return () => {
      setIOModalOpen(false);
    };
  }, [open]);

  function handleDeleteSession(session_id: string) {
    // Update UI optimistically
    if (visibleSession === session_id) {
      const remainingSessions = sessions.filter((s) => s !== session_id);
      if (remainingSessions.length > 0) {
        setvisibleSession(remainingSessions[0]);
      } else {
        setvisibleSession(currentFlowId);
      }
    }

    // Delete the session (which will delete all associated messages on the backend)
    deleteSessionFunction(
      { sessionId: session_id },
      {
        onSuccess: () => {
          // Remove the session from local state
          deleteSession(session_id);

          // Remove all messages for this session from local state
          const messageIdsToRemove = messages
            .filter((msg) => msg.session_id === session_id)
            .map((msg) => msg.id);

          if (messageIdsToRemove.length > 0) {
            removeMessages(messageIdsToRemove);
          }

          setSuccessData({
            title: "Session deleted successfully.",
          });
        },
        onError: () => {
          // Revert optimistic UI update on error
          if (visibleSession !== session_id) {
            setvisibleSession(session_id);
          }

          setErrorData({
            title: "Error deleting session.",
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
  const removeMessages = useMessagesStore((state) => state.removeMessages);
  const [sessions, setSessions] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState<string>(currentFlowId);
  const setCurrentSessionId = useUtilityStore(
    (state) => state.setCurrentSessionId,
  );

  const { isFetched: messagesFetched, refetch: refetchMessages } =
    useGetMessagesQuery(
      {
        mode: "union",
        id: currentFlowId,
        params: {
          session_id: visibleSession,
        },
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
          throw err;
        });
      }
    },
    [isBuilding, setIsBuilding, chatValue, chatInput?.id, sessionId, buildFlow],
  );

  useEffect(() => {
    if (newChatOnPlayground && !sessionsLoading) {
      const handleRefetchAndSetSession = async () => {
        try {
          const result = await refetchSessions();
          if (result.data?.sessions && result.data.sessions.length > 0) {
            setvisibleSession(
              result.data.sessions[result.data.sessions.length - 1],
            );
          }
        } catch (error) {
          console.error("Error refetching sessions:", error);
        }
      };

      handleRefetchAndSetSession();
      setNewChatOnPlayground(false);
    }
  }, [messages]);

  useEffect(() => {
    if (!visibleSession) {
      setSessionId(createNewSessionName());
      setCurrentSessionId(currentFlowId);
    } else if (visibleSession) {
      setSessionId(visibleSession);
      setCurrentSessionId(visibleSession);
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

  const showPublishOptions = playgroundPage && ENABLE_PUBLISH;

  const LangflowButtonClick = () => {
    track("LangflowButtonClick");
    customOpenNewTab(LangflowButtonRedirectTarget());
  };

  useEffect(() => {
    if (playgroundPage && messages.length > 0) {
      window.sessionStorage.setItem(currentFlowId, JSON.stringify(messages));
    }
  }, [playgroundPage, messages]);

  const swatchIndex =
    (flowGradient && !isNaN(parseInt(flowGradient))
      ? parseInt(flowGradient)
      : getNumberFromString(flowGradient ?? flowId ?? "")) %
    swatchColors.length;

  const setActiveSession = (session: string) => {
    setvisibleSession((prev) => {
      if (prev === session) {
        return undefined;
      }
      return session;
    });
  };

  const [hasInitialized, setHasInitialized] = useState(false);
  const prevVisibleSessionRef = useRef<string | undefined>(visibleSession);

  useEffect(() => {
    if (!hasInitialized) {
      setHasInitialized(true);
      prevVisibleSessionRef.current = visibleSession;
      return;
    }
    if (
      open &&
      visibleSession &&
      prevVisibleSessionRef.current !== visibleSession
    ) {
      refetchMessages();
    }

    prevVisibleSessionRef.current = visibleSession;
  }, [visibleSession]);

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      disable={disable}
      type={isPlayground ? "full-screen" : undefined}
      onSubmit={async () => await sendMessage({ repeat: 1 })}
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
                {sidebarOpen && !sessionsLoading && (
                  <SidebarOpenView
                    sessions={sessions}
                    setSelectedViewField={setSelectedViewField}
                    setvisibleSession={setvisibleSession}
                    handleDeleteSession={handleDeleteSession}
                    visibleSession={visibleSession}
                    selectedViewField={selectedViewField}
                    playgroundPage={!!playgroundPage}
                    setActiveSession={setActiveSession}
                  />
                )}
                {sidebarOpen && showPublishOptions && (
                  <div className="absolute bottom-2 left-0 flex w-full flex-col gap-8 border-t border-border px-2 py-4 transition-all">
                    <div className="flex items-center justify-between px-2">
                      <div className="text-sm">Theme</div>
                      <ThemeButtons />
                    </div>
                    <Button
                      onClick={LangflowButtonClick}
                      variant="primary"
                      className="w-full !rounded-xl shadow-lg"
                    >
                      <LangflowLogoColor />
                      <div className="text-sm">Built with Langflow</div>
                    </Button>
                  </div>
                )}
              </div>
            </div>
            {!sidebarOpen && showPublishOptions && (
              <div className="absolute bottom-6 left-4 hidden transition-all md:block">
                <ShadTooltip
                  styleClasses="z-50"
                  side="right"
                  content="Built with Langflow"
                >
                  <Button
                    variant="primary"
                    className="h-12 w-12 !rounded-xl !p-4 shadow-lg"
                    onClick={LangflowButtonClick}
                  >
                    <LangflowLogoColor className="h-[18px] w-[18px] scale-150" />
                  </Button>
                </ShadTooltip>
              </div>
            )}
            <div className="flex h-full min-w-96 flex-grow bg-background">
              {selectedViewField && !sessionsLoading && (
                <SelectedViewField
                  selectedViewField={selectedViewField}
                  setSelectedViewField={setSelectedViewField}
                  haveChat={haveChat}
                  inputs={filteredInputs}
                  outputs={filteredOutputs}
                  sessions={sessions}
                  currentFlowId={currentFlowId}
                  nodes={filteredNodes}
                />
              )}
              <ChatViewWrapper
                playgroundPage={playgroundPage}
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
                canvasOpen={canvasOpen}
                setOpen={setOpen}
                playgroundTitle={PlaygroundTitle}
              />
            </div>
          </div>
        )}
      </BaseModal.Content>
    </BaseModal>
  );
}
