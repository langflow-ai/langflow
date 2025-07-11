import { useStartConversation } from "@/modals/IOModal/components/chatView/chatInput/components/voice-assistant/hooks/use-start-conversation";

export const customUseStartConversation = (
  flowId: string,
  wsRef: React.MutableRefObject<WebSocket | null>,
  setStatus: (status: string) => void,
  handleWebSocketMessage: (event: MessageEvent) => void,
  stopRecording: () => void,
  currentSessionId: string,
) => {
  return useStartConversation(
    flowId,
    wsRef,
    setStatus,
    handleWebSocketMessage,
    stopRecording,
    currentSessionId,
  );
};

export default customUseStartConversation;
