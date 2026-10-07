import type { MutableRefObject } from "react";

export const useInitializeAudio = async (
  audioContextRef: MutableRefObject<AudioContext | null>,
  setStatus: (status: string) => void,
  startConversation: () => void,
  isCurrent: () => boolean = () => true,
): Promise<void> => {
  try {
    if (!isCurrent()) return;
    if (audioContextRef.current?.state === "closed") {
      audioContextRef.current = null;
    }

    if (!audioContextRef.current) {
      const AudioContextClass =
        window.AudioContext ||
        (window as Window & { webkitAudioContext?: typeof AudioContext })
          .webkitAudioContext;
      if (!AudioContextClass) {
        throw new Error("Web Audio API is unavailable");
      }
      audioContextRef.current = new AudioContextClass({
        sampleRate: 24000,
      });
    }

    if (audioContextRef.current.state === "suspended") {
      await audioContextRef.current.resume();
    }

    if (!isCurrent()) return;
    startConversation();
  } catch (error) {
    console.error("Failed to initialize audio:", error);
    setStatus("Error: Failed to initialize audio");
  }
};
