import IconComponent, {
  ForwardedIconComponent,
} from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import GlobalVariableModal from "@/components/core/GlobalVariableModal/GlobalVariableModal";
import InputComponent from "@/components/core/parameterRenderComponent/components/inputComponent";
import { getPlaceholder } from "@/components/core/parameterRenderComponent/helpers/get-placeholder-disabled";
import { Button } from "@/components/ui/button";
import { CommandItem } from "@/components/ui/command";
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
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { useVoiceStore } from "@/stores/voiceStore";
import { getLocalStorage, setLocalStorage } from "@/utils/local-storage-util";
import { cn } from "@/utils/utils";
import { useCallback, useEffect, useRef, useState } from "react";

interface SettingsVoiceModalProps {
  children?: React.ReactNode;
  open?: boolean;
  userOpenaiApiKey?: string;
}

const OPENAI_PROVIDER_LIST = [{ name: "OpenAI", value: "openai" }];
const FULL_PROVIDER_LIST = [
  ...OPENAI_PROVIDER_LIST,
  { name: "ElevenLabs", value: "elevenlabs" },
];

const SettingsVoiceModal = ({
  children,
  open: initialOpen = false,
  userOpenaiApiKey,
}: SettingsVoiceModalProps) => {
  const popupRef = useRef<HTMLDivElement>(null);
  const [provider, setProvider] = useState<string>("openai");
  const [voice, setVoice] = useState<string>("alloy");
  const [open, setOpen] = useState<boolean>(initialOpen);
  const voices = useVoiceStore((state) => state.voices);
  const shouldFetchVoices = voices.length === 0;
  const [openaiApiKey, setOpenaiApiKey] = useState<string>(userOpenaiApiKey!);

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

  const globalVariables = useGlobalVariablesStore(
    (state) => state.globalVariablesEntries,
  );

  console.log(openaiApiKey);

  return (
    <>
      <DropdownMenu open={open} onOpenChange={setOpen}>
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
                    optionsButton={
                      <GlobalVariableModal disabled={false}>
                        <CommandItem value="doNotFilter-addNewVariable">
                          <ForwardedIconComponent
                            name="Plus"
                            className={cn("mr-2 h-4 w-4 text-primary")}
                            aria-hidden="true"
                          />
                          <span>Add New Variable</span>
                        </CommandItem>
                      </GlobalVariableModal>
                    }
                    optionButton={(option) => (
                      <DeleteConfirmationModal
                        onConfirm={(e) => {
                          e.stopPropagation();
                          e.preventDefault();
                        }}
                        description={'variable "' + option + '"'}
                        asChild
                      >
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                          }}
                          className="pr-1"
                        >
                          <ForwardedIconComponent
                            name="Trash2"
                            className={cn(
                              "h-4 w-4 text-primary opacity-0 hover:text-status-red group-hover:opacity-100",
                            )}
                            aria-hidden="true"
                          />
                        </button>
                      </DeleteConfirmationModal>
                    )}
                    value={openaiApiKey}
                    onChange={(value) => {
                      setOpenaiApiKey(value);
                    }}
                    selectedOption={openaiApiKey}
                  />
                </div>

                <div className="grid w-full items-center gap-2">
                  <span className="flex items-center text-sm">
                    Voice Provider
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

                  <Select value={provider} onValueChange={handleProviderChange}>
                    <SelectTrigger className="w-full">
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
              </div>
            </div>
          </div>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
};

export default SettingsVoiceModal;
