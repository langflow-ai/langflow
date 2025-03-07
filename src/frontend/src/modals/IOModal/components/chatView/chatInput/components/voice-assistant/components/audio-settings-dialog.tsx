import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { useGetVoiceList } from "@/controllers/API/queries/voice/use-get-voice-list";
import { useVoiceStore } from "@/stores/voiceStore";
import { getLocalStorage, setLocalStorage } from "@/utils/local-storage-util";
import { useCallback, useEffect, useRef, useState } from "react";

interface SettingsVoiceModalProps {
  children?: React.ReactNode;
  open?: boolean;
}

const OPENAI_PROVIDER_LIST = [{ name: "OpenAI", value: "openai" }];
const FULL_PROVIDER_LIST = [
  ...OPENAI_PROVIDER_LIST,
  { name: "ElevenLabs", value: "elevenlabs" },
];

const SettingsVoiceModal = ({
  children,
  open: initialOpen = false,
}: SettingsVoiceModalProps) => {
  const popupRef = useRef<HTMLDivElement>(null);
  const [provider, setProvider] = useState<string>("openai");
  const [voice, setVoice] = useState<string>("alloy");
  const [open, setOpen] = useState<boolean>(initialOpen);
  const voices = useVoiceStore((state) => state.voices);
  const shouldFetchVoices = voices.length === 0;

  const providersList = useVoiceStore((state) => state.providersList);
  const setProvidersList = useVoiceStore((state) => state.setProvidersList);

  const openaiVoices = useVoiceStore((state) => state.openaiVoices);
  const [elevenLabsVoices, setElevenLabsVoices] = useState<
    { name: string; value: string }[]
  >([]);

  const { data: voiceList, isFetched } = useGetVoiceList({
    enabled: shouldFetchVoices,
    refetchOnMount: shouldFetchVoices,
    refetchOnWindowFocus: shouldFetchVoices,
    staleTime: Infinity,
  });

  useEffect(() => {
    if (isFetched && voiceList) {
      voiceList.length > 0
        ? setElevenLabsVoices(voiceList)
        : setElevenLabsVoices([]);

      setProviderList();
    }
  }, [voiceList, isFetched]);

  const setProviderList = () => {
    if (voiceList?.length === 0) {
      setProvidersList(OPENAI_PROVIDER_LIST);
    } else {
      setProvidersList(FULL_PROVIDER_LIST);
    }
  };

  const handleProviderChange = useCallback(
    (value: string) => {
      setProvider(value);
      if (value === "openai") {
        setVoice(openaiVoices[0].value);
      } else {
        setVoice(elevenLabsVoices[0].value);
      }
    },
    [openaiVoices, elevenLabsVoices],
  );

  const handleSubmit = useCallback(() => {
    setLocalStorage(
      "lf_audio_settings_playground",
      JSON.stringify({ provider, voice }),
    );
    setOpen(false);
  }, [provider, voice]);

  useEffect(() => {
    const audioSettings = JSON.parse(
      getLocalStorage("lf_audio_settings_playground") || "{}",
    );
    if (audioSettings.provider) {
      setProvider(audioSettings.provider);
      setVoice(audioSettings.voice);
    } else {
      setProvider(providersList[0].value);
      setVoice(openaiVoices[0].value);
    }
  }, [initialOpen]);

  return (
    <>
      <DropdownMenu open={open} onOpenChange={setOpen}>
        <DropdownMenuTrigger>{children}</DropdownMenuTrigger>
        <DropdownMenuContent>
          <div ref={popupRef}>
            <div>
              <div className="p-4">
                <span className="text-sm text-foreground">Audio Settings</span>
                <p className="text-[13px] text-muted-foreground">
                  Adjust the audio settings for the voice assistant.
                </p>
              </div>
              <Separator className="w-full" />

              <div className="space-y-4 p-4">
                <div className="flex items-center justify-between">
                  <span className="flex items-center font-[13px]">
                    Provider
                    <span className="ml-1 text-destructive">*</span>
                    <ShadTooltip content="The default provider is OpenAI.">
                      <div>
                        <IconComponent
                          name="Info"
                          strokeWidth={ICON_STROKE_WIDTH}
                          className="relative left-1 top-[1px] h-4 w-4 text-placeholder"
                        />
                      </div>
                    </ShadTooltip>
                  </span>

                  <Select value={provider} onValueChange={handleProviderChange}>
                    <SelectTrigger className="w-[170px]">
                      <SelectValue placeholder="Select" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {providersList.map((provider) => (
                          <SelectItem value={provider.value}>
                            {provider.name}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center justify-between">
                  <span className="flex items-center font-[13px]">
                    Voices
                    <span className="ml-1 text-destructive">*</span>
                    <ShadTooltip content={"The default voice is alloy."}>
                      <div>
                        <IconComponent
                          name="Info"
                          strokeWidth={ICON_STROKE_WIDTH}
                          className="relative left-1 top-[1px] h-4 w-4 text-placeholder"
                        />
                      </div>
                    </ShadTooltip>
                  </span>

                  <Select value={voice} onValueChange={setVoice}>
                    <SelectTrigger className="w-[170px]">
                      <SelectValue placeholder="Select" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {provider === "openai"
                          ? openaiVoices.map((voice) => (
                              <SelectItem value={voice.value}>
                                <div className="w-24 truncate text-left">
                                  {voice.name}
                                </div>
                              </SelectItem>
                            ))
                          : elevenLabsVoices.map((voice) => (
                              <SelectItem value={voice.value}>
                                <div className="w-24 truncate text-left">
                                  {voice.name}
                                </div>
                              </SelectItem>
                            ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>

                <Button
                  onClick={handleSubmit}
                  disabled={!provider?.trim() || !voice?.trim()}
                  className="w-full bg-primary"
                >
                  Save
                </Button>
              </div>
            </div>
          </div>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
};

export default SettingsVoiceModal;
