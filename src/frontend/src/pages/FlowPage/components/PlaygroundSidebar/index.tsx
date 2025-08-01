import { useCallback, useEffect, useRef, useState } from "react";
import { v5 as uuidv5 } from "uuid";
import { useShallow } from "zustand/react/shallow";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  useSidebar,
} from "@/components/ui/sidebar";
import {
  useGetMessagesQuery,
} from "@/controllers/API/queries/messages";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { useUtilityStore } from "@/stores/utilityStore";
import IconComponent from "../../../../components/common/genericIconComponent";
import ShadTooltip from "../../../../components/common/shadTooltipComponent";
import { Button } from "../../../../components/ui/button";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useMessagesStore } from "../../../../stores/messagesStore";
import { cn, getNumberFromString } from "../../../../utils/utils";
import { ChatViewWrapper } from "../../../../modals/IOModal/components/chat-view-wrapper";
import { createNewSessionName } from "../../../../modals/IOModal/components/chatView/chatInput/components/voice-assistant/helpers/create-new-session-name";

export function PlaygroundSidebar() {
  const { open, setOpen } = useSidebar();
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

  const { flowName } = useFlowStore(
    useShallow((state) => ({
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
  const clientId = useUtilityStore((state) => state.clientId);
  const realFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const currentFlowId = uuidv5(`${clientId}_${realFlowId}`, uuidv5.DNS);
  const setSidebarOpen = () => {}; // Placeholder since we removed sidebar functionality

  const [visibleSession, setvisibleSession] = useState<string | undefined>(
    currentFlowId,
  );
  const PlaygroundTitle = flowName ? flowName : "Playground";

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
      if (!sessions.includes(currentFlowId)) {
        sessions.unshift(currentFlowId);
      }
      setSessions(sessions);
    }
  }, [sessionsFromDb, sessionsLoading, currentFlowId]);



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
    if (messages.length > 0) {
      window.sessionStorage.setItem(currentFlowId, JSON.stringify(messages));
    }
  }, [messages]);

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
    <Sidebar
      side="right"
      collapsible="offcanvas"
      className="noflow select-none border-l"
    >
      <SidebarHeader className=" p-0 overflow-hidden">
        <div className="flex items-center justify-between gap-2 px-4 py-2">
          <div className="flex items-center gap-2">
            <div className="truncate text-sm font-medium text-secondary-foreground">
              Flow run {new Date().toLocaleDateString('en-US', { month: '2-digit', day: '2-digit' })} {new Date().toLocaleTimeString('en-US', { hour12: false })}
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="flex h-8 items-center gap-2 text-muted-foreground"
            >
              <IconComponent name="Plus" className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="flex h-8 items-center gap-2 text-muted-foreground"
            >
              <IconComponent name="History" className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="flex h-8 items-center gap-2 text-muted-foreground"
            >
              <IconComponent name="ExternalLink" className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="iconMd"
              className="flex h-8 items-center gap-2 text-muted-foreground"
            >
              <IconComponent name="MoreHorizontal" className="h-4 w-4" />
            </Button>
              <Button
                variant="ghost"
                size="iconMd"
              className="flex h-8 items-center gap-2 text-muted-foreground"
                onClick={() => setOpen(false)}
              >
                <IconComponent
                  name="X"
                  className="h-4 w-4"
                />
              </Button>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent className="p-0">
        <div className="flex h-full w-full bg-background">
          <ChatViewWrapper
            playgroundPage={true}
            selectedViewField={selectedViewField}
            visibleSession={visibleSession}
            sessions={sessions}
            sidebarOpen={false}
            currentFlowId={currentFlowId}
            setSidebarOpen={setSidebarOpen}
            isPlayground={true}
            setvisibleSession={setvisibleSession}
            setSelectedViewField={setSelectedViewField}
            haveChat={haveChat}
            messagesFetched={messagesFetched}
            sessionId={sessionId}
            sendMessage={sendMessage}
            canvasOpen={true}
            setOpen={setOpen}
            playgroundTitle={PlaygroundTitle}
          />
        </div>
      </SidebarContent>
    </Sidebar>
  );
}