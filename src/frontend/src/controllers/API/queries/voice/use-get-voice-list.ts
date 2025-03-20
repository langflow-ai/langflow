import { useVoiceStore } from "@/stores/voiceStore";
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetVoiceList: useQueryFunctionType<undefined, any> = (
  options,
) => {
  const { query } = UseRequestProcessor();
  const setVoices = useVoiceStore((state) => state.setVoices);
  const voices = useVoiceStore((state) => state.voices);

  const getVoiceListFn = async (): Promise<
    {
      name: string;
      voice_id: string;
    }[]
  > => {
    if (voices.length > 0) {
      return voices;
    }

    const res = await api.get(`${getURL("VOICE")}/elevenlabs/voice_ids`);
    const data = res.data;

    const voicesMapped = data.map((voice) => ({
      name: voice.name,
      value: voice.voice_id,
    }));

    setVoices(voicesMapped);
    return voicesMapped;
  };

  const defaultOptions = {
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    staleTime: 1000 * 60 * 5,
    ...options,
  };

  const queryResult = query(
    ["useGetVoiceList"],
    getVoiceListFn,
    defaultOptions,
  );
  return queryResult;
};
