import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { ICON_STROKE_WIDTH, SAVE_API_KEY_ALERT } from "@/constants/constants";
import { useGetMessagesPollingMutation } from "@/controllers/API/queries/messages/use-get-messages-polling";
import {
  useGetGlobalVariables,
  usePatchGlobalVariables,
  usePostGlobalVariables,
} from "@/controllers/API/queries/variables";
import { customUseStartConversation } from "@/customization/hooks/use-custom-start-conversation";
import { customUseStartRecording } from "@/customization/hooks/use-custom-start-recording";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { useMessagesStore } from "@/stores/messagesStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { useVoiceStore } from "@/stores/voiceStore";
import { cn } from "@/utils/utils";
import { useEffect, useMemo, useRef, useState } from "react";
import IconComponent from "../../../../../../../components/common/genericIconComponent";
import SettingsVoiceModal from "./components/audio-settings/audio-settings-dialog";
import { checkProvider } from "./helpers/check-provider";
import { formatTime } from "./helpers/format-time";
import { workletCode } from "./helpers/streamProcessor";
import { useBarControls } from "./hooks/use-bar-controls";
import { useHandleWebsocketMessage } from "./hooks/use-handle-websocket-message";
import { useInitializeAudio } from "./hooks/use-initialize-audio";
import { useInterruptPlayback } from "./hooks/use-interrupt-playback";
import { usePlayNextAudioChunk } from "./hooks/use-play-next-audio-chunk";
import { useStopRecording } from "./hooks/use-stop-recording";

export interface VoiceAssistantProps {
  flowId: string;
  setShowAudioInput: (value: boolean) => void;
}

export function VoiceAssistant({
  flowId,
  setShowAudioInput,
}: VoiceAssistantProps) {
  const [recordingTime, setRecordingTime] = useState(0);
  const [isRecording, setIsRecording] = useState(false);
  const [_status, setStatus] = useState("");
  const [_message, setMessage] = useState("");
  const [showSettingsModal, _setShowSettingsModal] = useState(false);
  const [addKey, setAddKey] = useState(false);
  const [barHeights, setBarHeights] = useState<number[]>(Array(30).fill(20));
  const [preferredLanguage, setPreferredLanguage] = useState(
    localStorage.getItem("lf_preferred_language") || "en-US",
  );
  const [isEditingOpenAIKey, setIsEditingOpenAIKey] = useState<boolean>(false);

  const waveformRef = useRef<HTMLDivElement>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const processorRef = useRef<AudioWorkletNode | null>(null);
  const audioQueueRef = useRef<AudioBuffer[]>([]);
  const isPlayingRef = useRef(false);
  const microphoneRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);

  const soundDetected = useVoiceStore((state) => state.soundDetected);
  const _setIsVoiceAssistantActive = useVoiceStore(
    (state) => state.setIsVoiceAssistantActive,
  );
  const setSoundDetected = useVoiceStore((state) => state.setSoundDetected);
  const messagesStore = useMessagesStore();
  const setIsBuilding = useFlowStore((state) => state.setIsBuilding);
  const edges = useFlowStore((state) => state.edges);
  const setEdges = useFlowStore((state) => state.setEdges);
  const updateBuildStatus = useFlowStore((state) => state.updateBuildStatus);
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
  const updateVariable = usePatchGlobalVariables();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const currentSessionId = useUtilityStore((state) => state.currentSessionId);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { data: globalVariables } = useGetGlobalVariables();
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const currentFlowId = currentFlow?.id;

  const hasOpenAIAPIKey = useMemo(() => {
    return (
      variables?.find((variable) => variable === "OPENAI_API_KEY")?.length! > 0
    );
  }, [variables, open, addKey]);

  const openaiApiKey = useMemo(() => {
    return variables?.find((variable) => variable === "OPENAI_API_KEY");
  }, [variables, addKey]);

  const openaiApiKeyGlobalVariable = useMemo(() => {
    return globalVariables?.find(
      (variable) => variable.name === "OPENAI_API_KEY",
    );
  }, [globalVariables]);

  const elevenLabsApiKeyGlobalVariable = useMemo(() => {
    return globalVariables?.find(
      (variable) => variable.name === "ELEVENLABS_API_KEY",
    );
  }, [globalVariables]);

  const hasElevenLabsApiKeyEnv = useMemo(() => {
    return Boolean(process.env?.ELEVENLABS_API_KEY);
  }, [variables, addKey]);

  useEffect(() => {
    if (!isRecording && hasOpenAIAPIKey && !showSettingsModal) {
      setIsRecording(true);
      initializeAudio();
    } else {
      stopRecording();
    }
  }, []);

  const getMessagesMutation = useGetMessagesPollingMutation();

  const initializeAudio = async () => {
    useInitializeAudio(audioContextRef, setStatus, startConversation);
  };

  const startRecording = async () => {
    customUseStartRecording(
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
      messagesStore,
      setEdges,
      addDataToFlowPool,
      updateEdgesRunningByNodes,
      updateBuildStatus,
      hasOpenAIAPIKey,
      showErrorAlert,
    );
  };

  const startConversation = () => {
    customUseStartConversation(
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

  useBarControls(
    isRecording,
    setRecordingTime,
    setBarHeights,
    analyserRef,
    setSoundDetected,
  );

  const handleGetMessagesMutation = () => {
    getMessagesMutation.mutate({
      mode: "union",
      id: currentFlowId,
    });
  };

  const showErrorAlert = (title: string, list: string[]) => {
    setErrorData({
      title,
      list,
    });
    setIsRecording(false);
  };

  const handleSaveApiKey = async (
    apiKey: string,
    variableName: string,
    elevenLabsKey: boolean,
  ) => {
    const updateOpenAiKey =
      isEditingOpenAIKey && openaiApiKeyGlobalVariable?.id;
    const updateElevenLabsApiKey =
      elevenLabsApiKeyGlobalVariable?.id && elevenLabsKey;

    if (updateOpenAiKey || updateElevenLabsApiKey) {
      await updateVariable.mutateAsync(
        {
          name: variableName,
          value: apiKey,
          id: elevenLabsKey
            ? elevenLabsApiKeyGlobalVariable?.id!
            : openaiApiKeyGlobalVariable?.id!,
        },
        {
          onSuccess: () => {
            setSuccessData({
              title: SAVE_API_KEY_ALERT,
            });
            setAddKey(!addKey);
            setIsEditingOpenAIKey(false);
          },
        },
      );
      return;
    }

    await createVariable.mutateAsync(
      {
        name: variableName,
        value: apiKey,
        type: "secret",
        default_fields: ["voice_mode"],
      },
      {
        onSuccess: () => {
          setSuccessData({
            title: SAVE_API_KEY_ALERT,
          });
          setAddKey(!addKey);
        },
      },
    );
  };

  useEffect(() => {
    checkProvider();
    handleGetMessagesMutation();

    return () => {
      stopRecording();
      if (audioContextRef.current) {
        audioContextRef.current.close();
        audioContextRef.current = null;
      }
    };
  }, [setShowAudioInput]);

  const scrollToBottom = () => {
    setTimeout(() => {
      const chatContainer = document.querySelector(".chat-message-div");
      if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
      }
    }, 300);
  };

  const handleCloseAudioInput = () => {
    setIsRecording(false);
    stopRecording();
    setShowAudioInput(false);
    scrollToBottom();
  };

  const handleSetShowSettingsModal = async (
    open: boolean,
    openaiApiKey: string,
    elevenLabsApiKey: string,
  ) => {
    const saveApiKey = openaiApiKey && openaiApiKey !== "OPENAI_API_KEY";
    const saveElevenLabsApiKey =
      elevenLabsApiKey && elevenLabsApiKey !== "ELEVENLABS_API_KEY";

    if (open) {
      stopRecording();
      if (audioContextRef.current) {
        audioContextRef.current.close();
        audioContextRef.current = null;
      }
      setIsRecording(false);
    } else {
      setRecordingTime(0);
      setBarHeights(Array(30).fill(20));

      if (hasOpenAIAPIKey) {
        if (audioContextRef.current) {
          audioContextRef.current.close();
          audioContextRef.current = null;
        }
        analyserRef.current = null;

        setTimeout(() => {
          initializeAudio();
          startRecording();
          setIsRecording(true);
        }, 100);
      }
    }

    if (saveApiKey) {
      await handleSaveApiKey(openaiApiKey, "OPENAI_API_KEY", false);
    }

    if (saveElevenLabsApiKey && !open) {
      await handleSaveApiKey(elevenLabsApiKey, "ELEVENLABS_API_KEY", true);
    }
  };

  const handleToggleRecording = () => {
    if (isRecording) {
      if (microphoneRef?.current && microphoneRef?.current?.mediaStream) {
        microphoneRef.current.mediaStream.getAudioTracks().forEach((track) => {
          track.enabled = false;
        });
      }
      setBarHeights(Array(30).fill(20));
      setIsRecording(false);
    } else {
      if (microphoneRef?.current && microphoneRef?.current?.mediaStream) {
        microphoneRef.current.mediaStream.getAudioTracks().forEach((track) => {
          track.enabled = true;
        });
      } else {
        startRecording();
      }
      setIsRecording(true);
    }
  };

  useEffect(() => {
    if (preferredLanguage) {
      localStorage.setItem("lf_preferred_language", preferredLanguage);
    }
  }, [preferredLanguage]);

  const handleClickSaveOpenAIApiKey = async (openaiApiKey: string) => {
    await handleSaveApiKey(openaiApiKey, "OPENAI_API_KEY", false);
  };

  return (
    <>
      <div
        data-testid="voice-assistant-container"
        className="mx-auto flex w-full max-w-[324px] items-center justify-center rounded-md border bg-background px-4 py-2 shadow-xl"
      >
        <div
          className={cn(
            "flex items-center",
            hasOpenAIAPIKey ? "gap-3" : "gap-2",
          )}
        >
          <ShadTooltip
            content={isRecording ? "Mute" : "Unmute"}
            delayDuration={500}
          >
            <Button unstyled onClick={handleToggleRecording}>
              <IconComponent
                name={isRecording ? "Mic" : "MicOff"}
                strokeWidth={ICON_STROKE_WIDTH}
                className="h-4 w-4 text-placeholder-foreground"
              />
            </Button>
          </ShadTooltip>

          <div
            ref={waveformRef}
            className="flex h-5 flex-1 items-center justify-center"
          >
            {barHeights.map((height, index) => (
              <div
                key={index}
                className={cn(
                  "mx-[1px] w-[2px] rounded-sm transition-all duration-200",
                  isRecording && soundDetected
                    ? "bg-red-foreground"
                    : "bg-placeholder-foreground",
                )}
                style={{ height: `${height}%` }}
              />
            ))}
          </div>
          <div className="min-w-[50px] cursor-default text-center font-mono text-sm font-medium text-placeholder-foreground">
            {hasOpenAIAPIKey ? formatTime(recordingTime) : "--:--s"}
          </div>

          <div>
            <SettingsVoiceModal
              userOpenaiApiKey={openaiApiKey}
              userElevenLabsApiKey={elevenLabsApiKeyGlobalVariable?.name}
              hasElevenLabsApiKeyEnv={hasElevenLabsApiKeyEnv}
              setShowSettingsModal={handleSetShowSettingsModal}
              hasOpenAIAPIKey={hasOpenAIAPIKey}
              language={preferredLanguage}
              setLanguage={setPreferredLanguage}
              handleClickSaveOpenAIApiKey={handleClickSaveOpenAIApiKey}
              isEditingOpenAIKey={isEditingOpenAIKey}
              setIsEditingOpenAIKey={setIsEditingOpenAIKey}
              isPlayingRef={isPlayingRef}
            >
              {hasOpenAIAPIKey ? (
                <>
                  <Button data-testid="voice-assistant-settings-icon" unstyled>
                    <IconComponent
                      name="Settings"
                      strokeWidth={ICON_STROKE_WIDTH}
                      className={cn(
                        "relative top-[2px] h-4 w-4 text-muted-foreground hover:text-foreground",
                      )}
                    />
                  </Button>
                </>
              ) : (
                <>
                  <Button
                    variant={"outlineAmber"}
                    size={"icon"}
                    data-testid="voice-assistant-settings-icon-without-openai"
                    className="h-8 w-8"
                  >
                    <IconComponent
                      name="Key"
                      strokeWidth={ICON_STROKE_WIDTH}
                      className={cn("h-4 w-4 text-accent-amber-foreground")}
                    />
                  </Button>
                </>
              )}
            </SettingsVoiceModal>
          </div>

          <Button
            unstyled
            onClick={handleCloseAudioInput}
            data-testid="voice-assistant-close-button"
          >
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
