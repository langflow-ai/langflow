import type { MutableRefObject } from "react";

export const useInterruptPlayback = (
  audioQueueRef: MutableRefObject<AudioBuffer[]>,
  isPlayingRef: MutableRefObject<boolean>,
  processorRef: MutableRefObject<AudioWorkletNode | null>,
) => {
  audioQueueRef.current.splice(0, audioQueueRef.current.length);
  isPlayingRef.current = false;
  if (processorRef.current) {
    processorRef.current.port.postMessage({ type: "stop_playback" });
  }
};
