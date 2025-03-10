import { Button } from "@/components/ui/button";
import { ICON_STROKE_WIDTH, SAVE_API_KEY_ALERT } from "@/constants/constants";
import { useGetMessagesMutation } from "@/controllers/API/queries/messages/use-get-messages-mutation";
import { usePostGlobalVariables } from "@/controllers/API/queries/variables";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { useMessagesStore } from "@/stores/messagesStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { getLocalStorage, setLocalStorage } from "@/utils/local-storage-util";
import { cn } from "@/utils/utils";
import { useEffect, useMemo, useRef, useState } from "react";
import IconComponent from "../../../../../../../components/common/genericIconComponent";
import AudioSettingsDialog from "./components/audio-settings-dialog";
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
  setShowAudioInput: (value: boolean) => void;
}

export function VoiceAssistant({
  flowId,
  setShowAudioInput,
}: VoiceAssistantProps) {
  const [recordingTime, setRecordingTime] = useState(0);
  const [isRecording, setIsRecording] = useState(false);
  const [status, setStatus] = useState("");
  const [message, setMessage] = useState("");
  const [showApiKeyModal, setShowApiKeyModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showSettingsButton, setShowSettingsButton] = useState(false);

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
  const currentSessionId = useUtilityStore((state) => state.currentSessionId);

  const hasOpenAIAPIKey = useMemo(() => {
    return (
      !variables?.find((variable) => variable === "OPENAI_API_KEY")?.length! > 0
    );
  }, [variables]);

  const openaiApiKey = useMemo(() => {
    return variables?.find((variable) => variable === "OPENAI_API_KEY");
  }, [variables]);

  const elevenLabsApiKey = useMemo(() => {
    return variables?.find((variable) => variable === "ELEVENLABS_API_KEY");
  }, [variables]);

  const getMessagesMutation = useGetMessagesMutation();

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
      handleGetMessagesMutation,
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
      currentSessionId,
    );
  };

  const interruptPlayback = () => {
    useInterruptPlayback(audioQueueRef, isPlayingRef, processorRef);
  };

  const handleGetMessagesMutation = () => {
    getMessagesMutation.mutate({
      mode: "union",
      id: currentSessionId,
    });
  };

  useEffect(() => {
    if (!hasOpenAIAPIKey) {
      setShowSettingsButton(true);
      return;
    }
    setShowSettingsButton(false);
    !isRecording ? initializeAudio() : stopRecording();
  }, [hasOpenAIAPIKey]);

  const toggleRecording = () => {
    if (!hasOpenAIAPIKey) {
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

  const waveformBars = useMemo(() => {
    return Array(30).fill(false);
  }, []);

  const waveformRef = useRef<HTMLDivElement>(null);

  const formatTime = (timeInSeconds: number): string => {
    const minutes = Math.floor(timeInSeconds / 60);
    const seconds = Math.floor(timeInSeconds % 60);
    return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}s`;
  };

  useEffect(() => {
    if (isRecording) {
      const interval = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [isRecording]);

  const handleCloseAudioInput = () => {
    stopRecording();
    setShowAudioInput(false);
  };

  return (
    <>
      <div className="mx-auto flex w-full max-w-[324px] items-center justify-center rounded-md border bg-background p-3 shadow-xl">
        <div
          className={cn(
            "flex items-center",
            showSettingsButton ? "gap-3" : "gap-5",
          )}
        >
          <IconComponent
            name="Mic"
            strokeWidth={ICON_STROKE_WIDTH}
            className="h-4 w-4 text-placeholder-foreground"
          />

          <div
            ref={waveformRef}
            className="flex h-5 flex-1 items-center justify-center"
          >
            {waveformBars.map((active, index) => (
              <div
                key={index}
                className={cn(
                  "mx-[1px] w-[2px] rounded-sm transition-all duration-200",
                  active && isRecording
                    ? "h-full bg-destructive"
                    : "h-[20%] bg-placeholder-foreground",
                )}
              />
            ))}
          </div>
          <div className="min-w-[50px] cursor-default text-center font-mono text-sm font-medium text-placeholder-foreground">
            {formatTime(recordingTime)}
          </div>

          {showSettingsButton && (
            <AudioSettingsDialog
              open={showSettingsModal}
              userOpenaiApiKey={openaiApiKey}
              userElevenLabsApiKey={elevenLabsApiKey}
            >
              <Button unstyled onClick={() => setShowSettingsModal(true)}>
                <IconComponent
                  name="Settings"
                  strokeWidth={ICON_STROKE_WIDTH}
                  className="h-4 w-4 text-muted-foreground hover:text-foreground"
                />
              </Button>
            </AudioSettingsDialog>
          )}

          <Button unstyled onClick={handleCloseAudioInput}>
            <IconComponent
              name="X"
              strokeWidth={ICON_STROKE_WIDTH}
              className="h-4 w-4 text-muted-foreground hover:text-foreground"
            />
          </Button>
        </div>
      </div>
    </>
  );
}
