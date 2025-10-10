import { getLocalStorage, setLocalStorage } from "@/utils/local-storage-util";

export const checkProvider = () => {
  const audioSettings = JSON.parse(
    getLocalStorage("lf_audio_settings_playground") || "{}",
  );
  if (!audioSettings?.provider) {
    setLocalStorage(
      "lf_audio_settings_playground",
      JSON.stringify({ provider: "openai", voice: "alloy" }),
    );
  }
};
