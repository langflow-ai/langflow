import { SAVE_API_KEY_ALERT } from "@/constants/constants";
import { usePostGlobalVariables } from "@/controllers/API/queries/variables";
import { PROXY_TARGET } from "@/customization/config-constants";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { useMessagesStore } from "@/stores/messagesStore";
import { getLocalStorage, setLocalStorage } from "@/utils/local-storage-util";
import { useEffect, useMemo, useRef, useState } from "react";
import ApiKeyPopUp from "./components/api-key-popup";
import SettingsVoiceModal from "./components/audio-settings-dialog";
import SettingsVoiceButton from "./components/settings-voice-button";
import VoiceButton from "./components/voice-button";
import { useHandleWebsocketMessage } from "./hooks/use-handle-websocket-message";
import { useInitializeAudio } from "./hooks/use-initialize-audio";
import { useInterruptPlayback } from "./hooks/use-interrupt-playback";
import { usePlayNextAudioChunk } from "./hooks/use-play-next-audio-chunk";
import { useStartConversation } from "./hooks/use-start-conversation";
import { useStartRecording } from "./hooks/use-start-recording";
import { useStopRecording } from "./hooks/use-stop-recording";
import { workletCode } from "./streamProcessor";
interface VoiceAssistantProps {
  flowId: string;
}

export function VoiceAssistant({ flowId }: VoiceAssistantProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [status, setStatus] = useState("");
  const [message, setMessage] = useState("");
  const [showApiKeyModal, setShowApiKeyModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);

  const audioContextRef = useRef<AudioContext | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const processorRef = useRef<AudioWorkletNode | null>(null);
  const audioQueueRef = useRef<AudioBuffer[]>([]);
  const isPlayingRef = useRef(false);
  const microphoneRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);

  const messagesStore = useMessagesStore();
  const setIsBuilding = useFlowStore((state) => state.setIsBuilding);
  const edges = useFlowStore((state) => state.edges);
  const setEdges = useFlowStore((state) => state.setEdges);
  const updateBuildStatus = useFlowStore((state) => state.updateBuildStatus);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const addDataToFlowPool = useFlowStore((state) => state.addDataToFlowPool);
  const updateEdgesRunningByNodes = useFlowStore(
    (state) => state.updateEdgesRunningByNodes,
  );
  const revertBuiltStatusFromBuilding = useFlowStore(
    (state) => state.revertBuiltStatusFromBuilding,
  );
  const clearEdgesRunningByNodes = useFlowStore(
    (state) => state.clearEdgesRunningByNodes,
  );
  const variables = useGlobalVariablesStore(
    (state) => state.globalVariablesEntries,
  );
  const createVariable = usePostGlobalVariables();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const hasOpenAIAPIKey = useMemo(() => {
    return (
      variables?.find((variable) => variable === "OPENAI_API_KEY")?.length! > 0
    );
  }, [variables]);

  const initializeAudio = async () => {
    useInitializeAudio(audioContextRef, setStatus, startConversation);
  };

  const startRecording = async () => {
    useStartRecording(
      audioContextRef,
      microphoneRef,
      analyserRef,
      wsRef,
      setIsRecording,
      playNextAudioChunk,
      isPlayingRef,
      audioQueueRef,
      workletCode,
      processorRef,
      setStatus,
    );
  };

  const stopRecording = () => {
    useStopRecording(
      microphoneRef,
      processorRef,
      analyserRef,
      wsRef,
      setIsRecording,
    );
  };

  const playNextAudioChunk = () => {
    usePlayNextAudioChunk(audioQueueRef, isPlayingRef, processorRef);
  };

  const handleWebSocketMessage = (event: MessageEvent) => {
    useHandleWebsocketMessage(
      event,
      interruptPlayback,
      audioContextRef,
      audioQueueRef,
      isPlayingRef,
      playNextAudioChunk,
      setIsBuilding,
      revertBuiltStatusFromBuilding,
      clearEdgesRunningByNodes,
      setMessage,
      edges,
      setStatus,
      setShowApiKeyModal,
      messagesStore,
      setEdges,
      addDataToFlowPool,
      updateEdgesRunningByNodes,
      updateBuildStatus,
      hasOpenAIAPIKey,
    );
  };

  const startConversation = () => {
    useStartConversation(
      flowId,
      wsRef,
      setStatus,
      startRecording,
      handleWebSocketMessage,
      stopRecording,
    );
  };

  const interruptPlayback = () => {
    useInterruptPlayback(audioQueueRef, isPlayingRef, processorRef);
  };

  const toggleRecording = () => {
    if (!hasOpenAIAPIKey) {
      setShowApiKeyModal(true);
      return;
    }
    !isRecording ? initializeAudio() : stopRecording();
    setIsRecording(!isRecording);
  };

  const handleSave = async (apiKey: string) => {
    try {
      await createVariable.mutateAsync({
        name: "OPENAI_API_KEY",
        value: apiKey,
        type: "secret",
        default_fields: ["voice_mode"],
      });
      setSuccessData({
        title: SAVE_API_KEY_ALERT,
      });
      setShowApiKeyModal(false);
    } catch (error) {
      console.error("Error saving API key:", error);
    }
  };

  const handleApiKeySubmit = (apiKey: string) => {
    if (!hasOpenAIAPIKey) {
      handleSave(apiKey);
      return;
    }

    if (!isRecording && hasOpenAIAPIKey) {
      initializeAudio();
    }
  };

  const checkProvider = () => {
    const audioSettings = JSON.parse(
      getLocalStorage("lf_audio_settings_playground") || "{}",
    );
    if (!audioSettings.provider) {
      setLocalStorage(
        "lf_audio_settings_playground",
        JSON.stringify({ provider: "openai", voice: "alloy" }),
      );
    }
  };

  useEffect(() => {
    checkProvider();

    return () => {
      stopRecording();
      if (audioContextRef.current) {
        audioContextRef.current.close();
        audioContextRef.current = null;
      }
    };
  }, []);

  return (
    <div className="">
      <div className="relative flex items-center gap-2">
        {status && (
          <div className="text-sm text-muted-foreground">{status}</div>
        )}
        {message && (
          <div className="text-sm text-muted-foreground">{message}</div>
        )}

        <SettingsVoiceModal open={showSettingsModal}>
          <SettingsVoiceButton
            isRecording={isRecording}
            setShowSettingsModal={setShowSettingsModal}
          />
        </SettingsVoiceModal>

        <ApiKeyPopUp
          isOpen={showApiKeyModal}
          onSubmit={handleApiKeySubmit}
          hasMessage={status || message}
        >
          <VoiceButton
            isRecording={isRecording}
            toggleRecording={toggleRecording}
            isBuilding={isBuilding}
          />
        </ApiKeyPopUp>
      </div>
    </div>
  );
}
