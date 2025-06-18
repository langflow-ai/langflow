import { useStartConversation } from "@/modals/IOModal/components/chatView/chatInput/components/voice-assistant/hooks/use-start-conversation";

export const customUseStartConversation = (
  flowId: string,
  wsRef: React.MutableRefObject<WebSocket | null>,
  setStatus: (status: string) => void,
  startRecording: () => void,
  handleWebSocketMessage: (event: MessageEvent) => void,
  stopRecording: () => void,
  currentSessionId: string,
) => {
  return useStartConversation(
    flowId,
    wsRef,
    setStatus,
    startRecording,
    handleWebSocketMessage,
    stopRecording,
    currentSessionId,
  );
};

export default customUseStartConversation;
