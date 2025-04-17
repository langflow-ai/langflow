export type VoiceStoreType = {
  voices: {
    name: string;
    voice_id: string;
  }[];
  setVoices: (
    voices: {
      name: string;
      voice_id: string;
    }[],
  ) => void;
  providersList: {
    name: string;
    value: string;
  }[];
  setProvidersList: (
    providersList: {
      name: string;
      value: string;
    }[],
  ) => void;
  openaiVoices: {
    name: string;
    value: string;
  }[];
  setOpenaiVoices: (
    openaiVoices: {
      name: string;
      value: string;
    }[],
  ) => void;
  soundDetected: boolean;
  setSoundDetected: (soundDetected: boolean) => void;
  isVoiceAssistantActive: boolean;
  setIsVoiceAssistantActive: (isVoiceAssistantActive: boolean) => void;
  newSessionCloseVoiceAssistant: boolean;
  setNewSessionCloseVoiceAssistant: (
    newSessionCloseVoiceAssistant: boolean,
  ) => void;
};
