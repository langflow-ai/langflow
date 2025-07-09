import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import InputComponent from "@/components/core/parameterRenderComponent/components/inputComponent";
import { getPlaceholder } from "@/components/core/parameterRenderComponent/helpers/get-placeholder-disabled";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import { usePatchGlobalVariables } from "@/controllers/API/queries/variables";
import { useGetVoiceList } from "@/controllers/API/queries/voice/use-get-voice-list";
import { useDebounce } from "@/hooks/use-debounce";
import GeneralDeleteConfirmationModal from "@/shared/components/delete-confirmation-modal";
import GeneralGlobalVariableModal from "@/shared/components/global-variable-modal";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { useVoiceStore } from "@/stores/voiceStore";
import { getLocalStorage, setLocalStorage } from "@/utils/local-storage-util";
import { useEffect, useRef, useState } from "react";
import AudioSettingsHeader from "./components/header";
import LanguageSelect from "./components/language-select";
import MicrophoneSelect from "./components/microphone-select";
import VoiceSelect from "./components/voice-select";

interface SettingsVoiceModalProps {
  children?: React.ReactNode;
  userOpenaiApiKey?: string;
  userElevenLabsApiKey?: string;
  hasElevenLabsApiKeyEnv?: boolean;
  setShowSettingsModal: (
    open: boolean,
    openaiApiKey: string,
    elevenLabsApiKey: string,
  ) => void;
  hasOpenAIAPIKey: boolean;
  language?: string;
  setLanguage?: (language: string) => void;
  handleClickSaveOpenAIApiKey: (openaiApiKey: string) => void;
  isEditingOpenAIKey: boolean;
  setIsEditingOpenAIKey: (isEditingOpenAIKey: boolean) => void;
  isPlayingRef: React.MutableRefObject<boolean>;
}

const SettingsVoiceModal = ({
  children,
  userOpenaiApiKey,
  userElevenLabsApiKey,
  setShowSettingsModal,
  hasOpenAIAPIKey,
  language,
  setLanguage,
  handleClickSaveOpenAIApiKey,
  isEditingOpenAIKey,
  setIsEditingOpenAIKey,
  isPlayingRef,
}: SettingsVoiceModalProps) => {
  const popupRef = useRef<HTMLDivElement>(null);
  const [voice, setVoice] = useState<string>("alloy");
  const [open, setOpen] = useState<boolean>(false);
  const voices = useVoiceStore((state) => state.voices);
  const shouldFetchVoices = voices.length === 0;
  const [openaiApiKey, setOpenaiApiKey] = useState<string>(
    userOpenaiApiKey ?? "",
  );
  const [elevenLabsApiKey, setElevenLabsApiKey] = useState<string>(
    userElevenLabsApiKey ?? "",
  );

  const globalVariables = useGlobalVariablesStore(
    (state) => state.globalVariablesEntries,
  );

  const globalVariablesEntities = useGlobalVariablesStore(
    (state) => state.globalVariablesEntities,
  );

  const openaiVoices = useVoiceStore((state) => state.openaiVoices);
  const [allVoices, setAllVoices] =
    useState<
      {
        name: string;
        value: string;
      }[]
    >(openaiVoices);

  const saveButtonClicked = useRef(false);

  const {
    data: voiceList,
    isFetched,
    refetch,
  } = useGetVoiceList(elevenLabsApiKey, {
    enabled: shouldFetchVoices,
    refetchOnMount: shouldFetchVoices,
    refetchOnWindowFocus: shouldFetchVoices,
    staleTime: Infinity,
  });

  const [microphones, setMicrophones] = useState<MediaDeviceInfo[]>([]);
  const [selectedMicrophone, setSelectedMicrophone] = useState<string>("");

  const [currentLanguage, setCurrentLanguage] = useState(
    localStorage.getItem("lf_preferred_language") || "en-US",
  );

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
  }, [voiceList, isFetched, userElevenLabsApiKey]);

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
  }, [isFetched]);

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

  const onOpenChangeDropdownMenu = (open: boolean) => {
    isPlayingRef.current = false;
    setOpen(open);
    setShowSettingsModal(open, openaiApiKey, elevenLabsApiKey);
  };

  const checkIfGlobalVariableExists = (variable: string) => {
    return globalVariables?.map((variable) => variable).includes(variable);
  };

  const { mutate: updateVariable } = usePatchGlobalVariables();

  const handleSetMicrophone = (deviceId: string) => {
    setSelectedMicrophone(deviceId);
    localStorage.setItem("lf_selected_microphone", deviceId);
  };

  useEffect(() => {
    setOpenaiApiKey(userOpenaiApiKey ?? "");
  }, [userOpenaiApiKey]);

  useEffect(() => {
    setElevenLabsApiKey(userElevenLabsApiKey ?? "");

    if (!userElevenLabsApiKey) {
      handleSetVoice(openaiVoices[0].value);
      setAllVoices(openaiVoices);
      return;
    }

    refetch();
  }, [userElevenLabsApiKey]);

  useEffect(() => {
    if (!hasOpenAIAPIKey) {
      setOpen(true);
    }
  }, [hasOpenAIAPIKey]);

  const handleSetLanguage = (value: string) => {
    setCurrentLanguage(value);
    localStorage.setItem("lf_preferred_language", value);
    if (setLanguage) {
      setLanguage(value);
    }
  };

  useEffect(() => {
    if (language) {
      setCurrentLanguage(language);
    }
  }, [language]);

  const handleClickSaveApiKey = (value: string) => {
    if (!value) return;
    if (value === "OPENAI_API_KEY") {
      setIsEditingOpenAIKey(false);
      return;
    }
    handleClickSaveOpenAIApiKey(value);
    saveButtonClicked.current = true;
  };

  const handleOpenAIKeyChange = (value: string) => {
    setOpenaiApiKey(value);
  };

  useEffect(() => {
    setOpenaiApiKey("");
  }, [isEditingOpenAIKey]);

  useEffect(() => {
    if (!open) {
      setIsEditingOpenAIKey(false);
    }
  }, [open]);

  const showAddOpenAIKeyButton = !hasOpenAIAPIKey || isEditingOpenAIKey;
  const showAllSettings = hasOpenAIAPIKey && !isEditingOpenAIKey;

  const debouncedSetElevenLabsApiKey = useDebounce((value: string) => {
    const globalVariable = globalVariablesEntities?.find(
      (variable) => variable.name === "ELEVENLABS_API_KEY",
    );

    if (globalVariable) {
      updateVariable({
        name: "ELEVENLABS_API_KEY",
        value: value,
        id: globalVariable.id,
      });
    }
  }, 2000);

  const handleSetElevenLabsApiKey = (value: string) => {
    setElevenLabsApiKey(value);
    debouncedSetElevenLabsApiKey(value);
  };

  return (
    <>
      <DropdownMenu open={open} onOpenChange={onOpenChangeDropdownMenu}>
        <DropdownMenuTrigger data-dropdown-trigger="true">
          {children}
        </DropdownMenuTrigger>
        <DropdownMenuContent
          className="w-[324px] rounded-xl shadow-lg"
          sideOffset={18}
          alignOffset={-60}
          align="end"
        >
          <div ref={popupRef} className="rounded-3xl">
            <div>
              <AudioSettingsHeader />
              <Separator className="w-full" />

              <div className="w-full space-y-4 p-4">
                <div className="grid w-full items-center gap-2">
                  <span className="flex items-center text-sm">
                    OpenAI API Key
                    <span className="ml-1 text-destructive">*</span>
                    <ShadTooltip content="OpenAI API key is required to use the voice assistant.">
                      <div>
                        <IconComponent
                          name="Info"
                          strokeWidth={2}
                          className="relative -top-[3px] left-1 h-[14px] w-[14px] text-placeholder"
                        />
                      </div>
                    </ShadTooltip>
                  </span>

                  {showAddOpenAIKeyButton && (
                    <>
                      <InputComponent
                        isObjectOption={false}
                        password
                        nodeStyle
                        popoverWidth="16rem"
                        placeholder={getPlaceholder(
                          false,
                          "Enter your OpenAI API key",
                        )}
                        id="openai-api-key"
                        options={
                          globalVariables?.map((variable) => variable) ?? []
                        }
                        optionsPlaceholder={"Global Variables"}
                        optionsIcon="Globe"
                        optionsButton={<GeneralGlobalVariableModal />}
                        optionButton={(option) => (
                          <GeneralDeleteConfirmationModal
                            option={option}
                            onConfirmDelete={() => {}}
                          />
                        )}
                        value={openaiApiKey}
                        onChange={handleOpenAIKeyChange}
                        selectedOption={
                          checkIfGlobalVariableExists(openaiApiKey)
                            ? openaiApiKey
                            : ""
                        }
                        commandWidth="11rem"
                      />
                    </>
                  )}

                  {showAllSettings && (
                    <>
                      <Button
                        variant="primary"
                        className="w-full"
                        onClick={() => setIsEditingOpenAIKey(true)}
                        size="md"
                      >
                        Edit
                      </Button>
                    </>
                  )}
                </div>

                {!showAllSettings && (
                  <div className="flex gap-2">
                    <Button
                      onClick={() => setIsEditingOpenAIKey(false)}
                      variant="primary"
                      size="md"
                      className="w-full"
                      data-testid="voice-assistant-settings-modal-cancel-button"
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={() => handleClickSaveApiKey(openaiApiKey)}
                      className="w-full"
                      disabled={!openaiApiKey}
                      size="md"
                      data-testid="voice-assistant-settings-modal-save-button"
                    >
                      {isEditingOpenAIKey ? "Update" : "Save"}
                    </Button>
                  </div>
                )}

                {showAllSettings && (
                  <>
                    <div className="grid w-full items-center gap-2">
                      <span className="flex items-center text-sm">
                        ElevenLabs API Key
                        <ShadTooltip content="If you have an ElevenLabs API key, you can select ElevenLabs voices.">
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
                        password
                        nodeStyle
                        popoverWidth="16rem"
                        placeholder={getPlaceholder(
                          false,
                          "Enter your ElevenLabs API key",
                        )}
                        id="eleven-labs-api-key"
                        options={
                          globalVariables?.map((variable) => variable) ?? []
                        }
                        optionsPlaceholder={"Global Variables"}
                        optionsIcon="Globe"
                        optionsButton={<GeneralGlobalVariableModal />}
                        optionButton={(option) => (
                          <GeneralDeleteConfirmationModal
                            option={option}
                            onConfirmDelete={() => {}}
                          />
                        )}
                        value={elevenLabsApiKey}
                        onChange={handleSetElevenLabsApiKey}
                        selectedOption={
                          checkIfGlobalVariableExists(elevenLabsApiKey)
                            ? elevenLabsApiKey
                            : ""
                        }
                        setSelectedOption={setElevenLabsApiKey}
                        commandWidth="11rem"
                        blockAddNewGlobalVariable
                      />
                    </div>

                    <VoiceSelect
                      voice={voice}
                      handleSetVoice={handleSetVoice}
                      allVoices={allVoices}
                    />

                    <MicrophoneSelect
                      selectedMicrophone={selectedMicrophone}
                      handleSetMicrophone={handleSetMicrophone}
                      microphones={microphones}
                      setMicrophones={setMicrophones}
                      setSelectedMicrophone={setSelectedMicrophone}
                    />

                    <LanguageSelect
                      language={currentLanguage}
                      handleSetLanguage={handleSetLanguage}
                    />
                  </>
                )}
              </div>
            </div>
          </div>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
};

export default SettingsVoiceModal;
