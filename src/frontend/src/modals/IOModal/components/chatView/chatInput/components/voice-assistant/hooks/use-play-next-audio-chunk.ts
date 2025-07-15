import type { MutableRefObject } from "react";

export const usePlayNextAudioChunk = (
  audioQueueRef: MutableRefObject<AudioBuffer[]>,
  isPlayingRef: MutableRefObject<boolean>,
  processorRef: MutableRefObject<AudioWorkletNode | null>,
) => {
  if (audioQueueRef.current.length === 0) {
    isPlayingRef.current = false;
    return;
  }

  isPlayingRef.current = true;
  const audioBuffer = audioQueueRef.current.shift();

  if (audioBuffer && processorRef.current) {
    try {
      processorRef.current.port.postMessage({
        type: "playback",
        audio: audioBuffer.getChannelData(0),
      });
    } catch (error) {
      console.error("Error playing audio:", error);
      isPlayingRef.current = false;
    }
  }
};
