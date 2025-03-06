import { getLocalStorage } from "@/utils/local-storage-util";

export const useStartConversation = (
  flowId: string,
  wsRef: React.MutableRefObject<WebSocket | null>,
  setStatus: (status: string) => void,
  startRecording: () => void,
  handleWebSocketMessage: (event: MessageEvent) => void,
  stopRecording: () => void,
  sessionId: string,
) => {
  try {
    // const url = `ws://${targetUrl}/api/v1/voice/ws/${flowId}`;
    const url = `ws://${window.location.hostname}:7860/api/v1/voice/ws/flow_as_tool/${flowId}/${sessionId}`;
    const audioSettings = JSON.parse(
      getLocalStorage("lf_audio_settings_playground") || "{}",
    );

    wsRef.current = new WebSocket(url);

    wsRef.current.onopen = () => {
      setStatus("Connected");
      if (wsRef.current) {
        wsRef.current.send(
          JSON.stringify({
            type: "elevenlabs.config",
            enabled: audioSettings.provider === "elevenlabs",
            voice_id: audioSettings.voice,
          }),
        );
      }
      startRecording();
    };

    wsRef.current.onmessage = handleWebSocketMessage;

    wsRef.current.onclose = (event) => {
      setStatus(`Disconnected (${event.code})`);
      stopRecording();
    };

    wsRef.current.onerror = (error) => {
      console.error("WebSocket Error:", error);
      setStatus("Connection error");
    };
  } catch (error) {
    console.error("Failed to create WebSocket:", error);
    setStatus("Connection failed");
  }
};
