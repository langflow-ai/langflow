//import LangflowLogoColor from "@/assets/LangflowLogocolor.svg?react";

import { useCallback, useEffect, useRef, useState } from "react";
import { v5 as uuidv5 } from "uuid";
import { useGetMessagesQuery } from "@/controllers/API/queries/messages";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useMessagesStore } from "@/stores/messagesStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { PlaygroundModalPropsType } from "@/types/components";
import ChatView from "./components/chatView/components/chat-view";
import { PlaygroundHeader } from "./components/playgroundHeader/playground-header";

export function PlaygroundComponent({
  playgroundPage,
  onClose,
}: PlaygroundModalPropsType): JSX.Element {
  const inputs = useFlowStore((state) => state.inputs);
  const buildFlow = useFlowStore((state) => state.buildFlow);
  const setIsBuilding = useFlowStore((state) => state.setIsBuilding);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const chatInput = inputs.find((input) => input.type === "ChatInput");
  const clientId = useUtilityStore((state) => state.clientId);
  const realFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const currentFlowId = playgroundPage
    ? uuidv5(`${clientId}_${realFlowId}`, uuidv5.DNS)
    : realFlowId;

  const messages = useMessagesStore((state) => state.messages);

  const selectedSession = usePlaygroundStore((state) => state.selectedSession);
  const setSelectedSession = usePlaygroundStore(
    (state) => state.setSelectedSession
  );
  const { data: sessions, refetch: refetchSessions } =
    useGetSessionsFromFlowQuery({
      flowId: currentFlowId,
      useLocalStorage: playgroundPage,
    });

  const { isFetched: messagesFetched, refetch: refetchMessages } =
    useGetMessagesQuery({
      mode: "union",
      id: currentFlowId,
      params: {
        session_id: selectedSession,
      },
    });

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
          session: selectedSession,
          eventDelivery: eventDeliveryConfig,
        }).catch((err) => {
          console.error(err);
          throw err;
        });
        if (selectedSession && !sessions?.includes(selectedSession)) {
          refetchSessions();
        }
      }
    },
    [
      isBuilding,
      setIsBuilding,
      chatValue,
      chatInput?.id,
      selectedSession,
      buildFlow,
    ]
  );

  const setPlaygroundScrollBehaves = useUtilityStore(
    (state) => state.setPlaygroundScrollBehaves
  );

  useEffect(() => {
    setPlaygroundScrollBehaves("instant");
    setSelectedSession(currentFlowId);
  }, []);

  useEffect(() => {
    if (playgroundPage && messages.length > 0) {
      window.sessionStorage.setItem(currentFlowId, JSON.stringify(messages));
    }
  }, [playgroundPage, messages]);

  const [hasInitialized, setHasInitialized] = useState(false);
  const prevVisibleSessionRef = useRef<string | undefined>(selectedSession);

  useEffect(() => {
    if (!hasInitialized) {
      setHasInitialized(true);
      prevVisibleSessionRef.current = selectedSession;
      return;
    }
    if (selectedSession && prevVisibleSessionRef.current !== selectedSession) {
      refetchMessages();
    }

    prevVisibleSessionRef.current = selectedSession;
  }, [selectedSession]);

  return (
    <div className="flex flex-col w-full h-full">
      <PlaygroundHeader onClose={onClose} />
      <div className="flex container flex-grow p-4">
        <ChatView
          sendMessage={sendMessage}
          visibleSession={selectedSession}
          playgroundPage={playgroundPage}
        />
      </div>
    </div>
  );
}
