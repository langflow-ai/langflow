import { OPENAI_VOICES } from "@/constants/constants";
import type { VoiceStoreType } from "@/types/zustand/voice/voice.types";
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
  openaiVoices: OPENAI_VOICES,
  setOpenaiVoices: (
    openaiVoices: {
      name: string;
      value: string;
    }[],
  ) => set({ openaiVoices }),
  soundDetected: false,
  setSoundDetected: (soundDetected: boolean) => set({ soundDetected }),
  isVoiceAssistantActive: false,
  setIsVoiceAssistantActive: (isVoiceAssistantActive: boolean) =>
    set({ isVoiceAssistantActive }),
  newSessionCloseVoiceAssistant: false,
  setNewSessionCloseVoiceAssistant: (newSessionCloseVoiceAssistant: boolean) =>
    set({ newSessionCloseVoiceAssistant }),
}));
