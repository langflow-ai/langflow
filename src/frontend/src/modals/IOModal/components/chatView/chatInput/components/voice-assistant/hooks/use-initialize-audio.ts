import { MutableRefObject } from "react";

export const useInitializeAudio = async (
  audioContextRef: MutableRefObject<AudioContext | null>,
  setStatus: (status: string) => void,
  startConversation: () => void,
): Promise<void> => {
  try {
    // Close existing context if it exists
    if (audioContextRef.current?.state === "closed") {
      audioContextRef.current = null;
    }

    // Create new context if needed
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext ||
        (window as any).webkitAudioContext)({
        sampleRate: 24000,
      });
    }

    // Only resume if context is in suspended state
    if (audioContextRef.current.state === "suspended") {
      await audioContextRef.current.resume();
    }

    startConversation();
  } catch (error) {
    console.error("Failed to initialize audio:", error);
    setStatus("Error: Failed to initialize audio");
  }
};
