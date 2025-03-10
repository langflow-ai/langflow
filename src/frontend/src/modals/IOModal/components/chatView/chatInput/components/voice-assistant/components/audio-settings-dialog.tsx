import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import InputComponent from "@/components/core/parameterRenderComponent/components/inputComponent";
import { getPlaceholder } from "@/components/core/parameterRenderComponent/helpers/get-placeholder-disabled";
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
import GeneralDeleteConfirmationModal from "@/shared/components/delete-confirmation-modal";
import GeneralGlobalVariableModal from "@/shared/components/global-variable-modal";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { useVoiceStore } from "@/stores/voiceStore";
import { getLocalStorage, setLocalStorage } from "@/utils/local-storage-util";
import { toTitleCase } from "@/utils/utils";
import { useEffect, useRef, useState } from "react";

interface SettingsVoiceModalProps {
  children?: React.ReactNode;
  open?: boolean;
  userOpenaiApiKey?: string;
  userElevenLabsApiKey?: string;
  hasElevenLabsApiKeyEnv?: boolean;
  setShowSettingsModal: (open: boolean) => void;
}

const SettingsVoiceModal = ({
  children,
  open: initialOpen = false,
  userOpenaiApiKey,
  userElevenLabsApiKey,
  setShowSettingsModal,
}: SettingsVoiceModalProps) => {
  const popupRef = useRef<HTMLDivElement>(null);
  const [voice, setVoice] = useState<string>("alloy");
  const [open, setOpen] = useState<boolean>(initialOpen);
  const voices = useVoiceStore((state) => state.voices);
  const shouldFetchVoices = voices.length === 0;
  const [openaiApiKey, setOpenaiApiKey] = useState<string>(userOpenaiApiKey!);
  const [elevenLabsApiKey, setElevenLabsApiKey] = useState<string>(
    userElevenLabsApiKey!,
  );

  const globalVariables = useGlobalVariablesStore(
    (state) => state.globalVariablesEntries,
  );

  const openaiVoices = useVoiceStore((state) => state.openaiVoices);
  const [allVoices, setAllVoices] = useState<
    {
      name: string;
      value: string;
    }[]
  >([]);

  const { data: voiceList, isFetched } = useGetVoiceList({
    enabled: shouldFetchVoices,
    refetchOnMount: shouldFetchVoices,
    refetchOnWindowFocus: shouldFetchVoices,
    staleTime: Infinity,
  });

  useEffect(() => {
    if (isFetched) {
      if (voiceList) {
        const allVoicesMerged = [...openaiVoices, ...voiceList];

        voiceList.length > 0
          ? setAllVoices(allVoicesMerged)
          : setAllVoices(openaiVoices);
      } else {
        setAllVoices(openaiVoices);
      }
    }
  }, [voiceList, isFetched]);

  useEffect(() => {
    const audioSettings = JSON.parse(
      getLocalStorage("lf_audio_settings_playground") || "{}",
    );
    if (isFetched) {
      if (audioSettings.provider) {
        setVoice(audioSettings.voice);
      } else {
        setVoice(openaiVoices[0].value);
      }
    } else {
      setVoice(openaiVoices[0].value);
    }
  }, [initialOpen, isFetched]);

  const handleSetVoice = (value: string) => {
    setVoice(value);
    const isOpenAiVoice = openaiVoices.some((voice) => voice.value === value);
    if (isOpenAiVoice) {
      setLocalStorage(
        "lf_audio_settings_playground",
        JSON.stringify({
          provider: "openai",
          voice: value,
        }),
      );
    } else {
      setLocalStorage(
        "lf_audio_settings_playground",
        JSON.stringify({
          provider: "elevenlabs",
          voice: value,
        }),
      );
    }
  };

  const handleSetOpen = (open: boolean) => {
    setOpen(open);
    setShowSettingsModal(open);
  };

  return (
    <>
      <DropdownMenu open={open} onOpenChange={handleSetOpen}>
        <DropdownMenuTrigger>{children}</DropdownMenuTrigger>
        <DropdownMenuContent
          className="w-[324px]"
          sideOffset={18}
          alignOffset={-55}
          align="end"
        >
          <div ref={popupRef} className="rounded-3xl">
            <div>
              <div className="grid gap-1 p-4">
                <p className="flex items-center gap-2 text-sm text-primary">
                  <IconComponent
                    name="Settings"
                    strokeWidth={ICON_STROKE_WIDTH}
                    className="h-4 w-4 text-muted-foreground hover:text-foreground"
                  />
                  Voice settings
                </p>
                <p className="text-[13px] leading-4 text-muted-foreground">
                  Voice chat is powered by OpenAI. You can also add more voices
                  with ElevenLabs.
                </p>
              </div>
              <Separator className="w-full" />

              <div className="w-full space-y-4 p-4">
                <div className="grid w-full items-center gap-2">
                  <span className="flex items-center text-sm">
                    OpenAI API Key
                    <span className="ml-1 text-destructive">*</span>
                    <ShadTooltip content="The default provider is OpenAI.">
                      <div>
                        <IconComponent
                          name="Info"
                          strokeWidth={2}
                          className="relative -top-[3px] left-1 h-[14px] w-[14px] text-placeholder"
                        />
                      </div>
                    </ShadTooltip>
                  </span>

                  <InputComponent
                    isObjectOption={false}
                    password={false}
                    nodeStyle
                    popoverWidth="16rem"
                    placeholder={getPlaceholder(
                      false,
                      "Enter your OpenAI API key",
                    )}
                    id="openai-api-key"
                    options={globalVariables?.map((variable) => variable) ?? []}
                    optionsPlaceholder={"Global Variables"}
                    optionsIcon="Globe"
                    optionsButton={<GeneralGlobalVariableModal />}
                    optionButton={(option) => (
                      <GeneralDeleteConfirmationModal option={option} />
                    )}
                    value={openaiApiKey}
                    onChange={(value) => {
                      setOpenaiApiKey(value);
                    }}
                    selectedOption={openaiApiKey}
                    setSelectedOption={setOpenaiApiKey}
                  />
                </div>

                <div className="grid w-full items-center gap-2">
                  <span className="flex items-center text-sm">
                    ElevenLabs API Key
                    <ShadTooltip content="The default provider is OpenAI.">
                      <div>
                        <IconComponent
                          name="Info"
                          strokeWidth={2}
                          className="relative -top-[3px] left-1 h-[14px] w-[14px] text-placeholder"
                        />
                      </div>
                    </ShadTooltip>
                  </span>

                  <InputComponent
                    isObjectOption={false}
                    password={false}
                    nodeStyle
                    popoverWidth="16rem"
                    placeholder={getPlaceholder(
                      false,
                      "Enter your ElevenLabs API key",
                    )}
                    id="eleven-labs-api-key"
                    options={globalVariables?.map((variable) => variable) ?? []}
                    optionsPlaceholder={"Global Variables"}
                    optionsIcon="Globe"
                    optionsButton={<GeneralGlobalVariableModal />}
                    optionButton={(option) => (
                      <GeneralDeleteConfirmationModal option={option} />
                    )}
                    value={elevenLabsApiKey}
                    onChange={(value) => {
                      setElevenLabsApiKey(value);
                    }}
                    selectedOption={elevenLabsApiKey}
                    setSelectedOption={setElevenLabsApiKey}
                  />
                </div>

                <div className="grid w-full items-center gap-2">
                  <span className="flex w-full items-center text-sm">
                    Voice
                    <ShadTooltip content="You can select ElevenLabs voices if you have an ElevenLabs API key. Otherwise, you can only select OpenAI voices.">
                      <div>
                        <IconComponent
                          name="Info"
                          strokeWidth={2}
                          className="relative -top-[3px] left-1 h-[14px] w-[14px] text-placeholder"
                        />
                      </div>
                    </ShadTooltip>
                  </span>

                  <Select value={voice} onValueChange={handleSetVoice}>
                    <SelectTrigger className="h-9 w-full">
                      <SelectValue placeholder="Select" />
                    </SelectTrigger>
                    <SelectContent className="max-h-[200px]">
                      <SelectGroup>
                        {allVoices.map((voice) => (
                          <SelectItem value={voice.value}>
                            <div className="truncate text-left">
                              {toTitleCase(voice.name)}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          </div>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
};

export default SettingsVoiceModal;
