import { useStartRecording } from "@/modals/IOModal/components/chatView/chatInput/components/voice-assistant/hooks/use-start-recording";
import type { MutableRefObject } from "react";

export const customUseStartRecording = (
  audioContextRef: React.MutableRefObject<AudioContext | null>,
  microphoneRef: MutableRefObject<MediaStreamAudioSourceNode | null>,
  analyserRef: React.MutableRefObject<AnalyserNode | null>,
  wsRef: React.MutableRefObject<WebSocket | null>,
  setIsRecording: (isRecording: boolean) => void,
  playNextAudioChunk: () => void,
  isPlayingRef: React.MutableRefObject<boolean>,
  audioQueueRef: MutableRefObject<AudioBuffer[]>,
  workletCode: string,
  processorRef: MutableRefObject<AudioWorkletNode | null>,
  setStatus: (status: string) => void,
) => {
  return useStartRecording(
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

export default customUseStartRecording;
