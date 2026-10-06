import i18n from "@/i18n";
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
      const previousSocket = wsRef.current;
      wsRef.current = null;
      previousSocket.onopen = null;
      previousSocket.onmessage = null;
      previousSocket.onerror = null;
      previousSocket.onclose = null;
      previousSocket.close();
    }

    const audioSettings = JSON.parse(
      getLocalStorage("lf_audio_settings_playground") || "{}",
    );
    const _audioLanguage =
      getLocalStorage("lf_audio_language_playground") || "en-US";

    const socket = new WebSocket(url);
    wsRef.current = socket;

    socket.onopen = () => {
      if (wsRef.current !== socket) {
        socket.close();
        return;
      }
      setStatus(i18n.t("voiceAssistant.connected"));
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(
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
          socket.send(
            JSON.stringify({
              type: "voice.settings",
              voice: audioSettings.voice || "echo",
              provider: audioSettings.provider || "openai",
            }),
          );
        }
        setTimeout(() => {
          if (
            wsRef.current === socket &&
            socket.readyState === WebSocket.OPEN
          ) {
            startRecording();
          }
        }, 300);
      }
    };

    socket.onmessage = (event) => {
      if (wsRef.current === socket) {
        handleWebSocketMessage(event);
      }
    };

    socket.onclose = (event) => {
      if (wsRef.current !== socket) return;
      wsRef.current = null;
      if (event.code !== 1000) {
        // 1000 is normal closure
        console.warn(`WebSocket closed with code ${event.code}`);
      }
      setStatus(`Disconnected (${event.code})`);
      stopRecording();
    };

    socket.onerror = (error) => {
      if (wsRef.current !== socket) return;
      console.error("WebSocket Error:", error);
      setStatus(i18n.t("voiceAssistant.connectionError"));
      stopRecording();
      if (wsRef.current === socket) {
        wsRef.current = null;
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;
        socket.close();
      }
    };
  } catch (error) {
    console.error("Failed to create WebSocket:", error);
    setStatus(i18n.t("voiceAssistant.connectionFailed"));
    stopRecording();
  }
};
