import { getLocalStorage } from "@/utils/local-storage-util";

export const useStartConversation = (
  flowId: string,
  wsRef: React.MutableRefObject<WebSocket | null>,
  setStatus: (status: string) => void,
  startRecording: () => void,
  handleWebSocketMessage: (event: MessageEvent) => void,
  stopRecording: () => void,
  currentSessionId: string,
) => {
  const currentHost = window.location.hostname;
  const currentPort = window.location.port;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const url = `${protocol}//${currentHost}:${currentPort}/api/v1/voice/ws/flow_tts/${flowId}/${currentSessionId?.toString()}`;
  //const url = `${protocol}//${currentHost}:${currentPort}/api/v1/voice/ws/flow_as_tool/${flowId}/${currentSessionId?.toString()}`;

  try {
    if (wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }

    const audioSettings = JSON.parse(
      getLocalStorage("lf_audio_settings_playground") || "{}",
    );
    const _audioLanguage =
      getLocalStorage("lf_audio_language_playground") || "en-US";

    wsRef.current = new WebSocket(url);

    wsRef.current.onopen = () => {
      setStatus("Connected");
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: "langflow.elevenlabs.config",
            enabled: audioSettings.provider === "elevenlabs",
            voice_id:
              audioSettings.provider === "elevenlabs"
                ? audioSettings.voice
                : "",
          }),
        );

        // For flow_tts endpoint, we need to use the proper session update format
        if (audioSettings.provider !== "elevenlabs") {
          wsRef.current.send(
            JSON.stringify({
              type: "voice.settings",
              voice: audioSettings.voice || "echo",
              provider: audioSettings.provider || "openai",
            }),
          );
        }
        setTimeout(() => {
          startRecording();
        }, 300);
      }
    };

    wsRef.current.onmessage = handleWebSocketMessage;

    wsRef.current.onclose = (event) => {
      if (event.code !== 1000) {
        // 1000 is normal closure
        console.warn(`WebSocket closed with code ${event.code}`);
      }
      setStatus(`Disconnected (${event.code})`);
      stopRecording();
    };

    wsRef.current.onerror = (error) => {
      console.error("WebSocket Error:", error);
      setStatus("Connection error");
      stopRecording();
    };
  } catch (error) {
    console.error("Failed to create WebSocket:", error);
    setStatus("Connection failed");
    stopRecording();
  }
};
