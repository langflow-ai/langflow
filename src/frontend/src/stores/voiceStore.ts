import { VoiceStoreType } from "@/types/zustand/voice/voice.types";
import { create } from "zustand";

export const useVoiceStore = create<VoiceStoreType>((set, get) => ({
  voices: [],
  setVoices: (
    voices: {
      name: string;
      voice_id: string;
    }[],
  ) => set({ voices }),
  providersList: [
    { name: "OpenAI", value: "openai" },
    { name: "ElevenLabs", value: "elevenlabs" },
  ],
  setProvidersList: (
    providersList: {
      name: string;
      value: string;
    }[],
  ) => set({ providersList }),
  openaiVoices: [
    { name: "alloy", value: "alloy" },
    { name: "ash", value: "ash" },
    { name: "ballad", value: "ballad" },
    { name: "coral", value: "coral" },
    { name: "echo", value: "echo" },
    { name: "sage", value: "sage" },
    { name: "shimmer", value: "shimmer" },
    { name: "verse", value: "verse" },
  ],
  setOpenaiVoices: (
    openaiVoices: {
      name: string;
      value: string;
    }[],
  ) => set({ openaiVoices }),
  soundDetected: false,
  setSoundDetected: (soundDetected: boolean) => set({ soundDetected }),
}));
