import { useEffect, useRef } from "react";

interface ScopedVoiceInitializationOptions {
  flowId: string;
  hasOpenAIAPIKey: boolean;
  scopedCredentialsReady: boolean;
  showSettingsModal: boolean;
  initializeAudio: (isCurrent: () => boolean) => void | Promise<void>;
  stopRecording: () => void;
  setIsRecording: (isRecording: boolean) => void;
}

export function useScopedVoiceInitialization({
  flowId,
  hasOpenAIAPIKey,
  scopedCredentialsReady,
  showSettingsModal,
  initializeAudio,
  stopRecording,
  setIsRecording,
}: ScopedVoiceInitializationOptions) {
  const initializedFlowIdRef = useRef<string | null>(null);
  const generationRef = useRef(0);
  const initializeAudioRef = useRef(initializeAudio);
  const setIsRecordingRef = useRef(setIsRecording);
  const stopRecordingRef = useRef(stopRecording);
  initializeAudioRef.current = initializeAudio;
  setIsRecordingRef.current = setIsRecording;
  stopRecordingRef.current = stopRecording;

  useEffect(() => {
    const generation = ++generationRef.current;
    const invalidateGeneration = () => {
      if (generationRef.current === generation) {
        generationRef.current += 1;
      }
    };

    if (
      !flowId ||
      !scopedCredentialsReady ||
      !hasOpenAIAPIKey ||
      showSettingsModal
    ) {
      initializedFlowIdRef.current = null;
      stopRecordingRef.current();
      return invalidateGeneration;
    }

    if (initializedFlowIdRef.current === flowId) {
      return invalidateGeneration;
    }
    if (initializedFlowIdRef.current !== null) {
      stopRecordingRef.current();
    }
    initializedFlowIdRef.current = flowId;
    setIsRecordingRef.current(true);
    void initializeAudioRef.current(() => generationRef.current === generation);
    return invalidateGeneration;
  }, [flowId, hasOpenAIAPIKey, scopedCredentialsReady, showSettingsModal]);

  useEffect(
    () => () => {
      generationRef.current += 1;
      initializedFlowIdRef.current = null;
      stopRecordingRef.current();
    },
    [],
  );
}
