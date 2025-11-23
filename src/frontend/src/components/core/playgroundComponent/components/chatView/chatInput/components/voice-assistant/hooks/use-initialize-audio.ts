import type { MutableRefObject } from "react";

export const useInitializeAudio = async (
  audioContextRef: MutableRefObject<AudioContext | null>,
  setStatus: (status: string) => void,
  startConversation: () => void,
): Promise<void> => {
  try {
    if (audioContextRef.current?.state === "closed") {
      audioContextRef.current = null;
    }

    if (!audioContextRef.current) {
      audioContextRef.current = new (
        window.AudioContext || (window as any).webkitAudioContext
      )({
        sampleRate: 24000,
      });
    }

    if (audioContextRef.current.state === "suspended") {
      await audioContextRef.current.resume();
    }

    startConversation();
  } catch (error) {
    console.error("Failed to initialize audio:", error);
    setStatus("Error: Failed to initialize audio");
  }
};
