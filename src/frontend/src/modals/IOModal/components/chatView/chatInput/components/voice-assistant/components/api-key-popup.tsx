import IconComponent from "@/components/common/genericIconComponent";
import InputComponent from "@/components/core/parameterRenderComponent/components/inputComponent";
import InputGlobalComponent from "@/components/core/parameterRenderComponent/components/inputGlobalComponent";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { FC, useEffect, useRef, useState } from "react";

interface ApiKeyPopupProps {
  onSubmit: (apiKey: string) => void;
  onClose?: () => void;
  isOpen: boolean;
  hasMessage?: string;
}

const ApiKeyPopup: FC<ApiKeyPopupProps> = ({
  onSubmit,
  onClose,
  isOpen,
  hasMessage,
}) => {
  const [apiKey, setApiKey] = useState<string>("");
  const popupRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const globalVariableModalOpen = document.getElementById(
        "global-variable-modal-inputs",
      );

      if (
        popupRef.current &&
        !popupRef.current.contains(event.target as Node) &&
        onClose &&
        !globalVariableModalOpen
      ) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleSubmit = () => {
    onSubmit(apiKey);
  };

  return (
    <>
      {isOpen && (
        <div
          className={`fixed z-[99] flex w-[420px] -translate-y-[19rem] ${
            hasMessage ? "-translate-x-40" : "-translate-x-80"
          } items-center justify-center`}
        >
          <div
            ref={popupRef}
            className="mx-4 w-full max-w-md overflow-hidden rounded-2xl border-2 border-border bg-background shadow-lg"
          >
            <div>
              <div className="p-4">
                <span className="text-sm text-foreground">
                  Enable Voice Transcription
                </span>
                <p className="text-[13px] text-muted-foreground">
                  Voice transcription is powered by OpenAI. To enable it, enter
                  your API key.
                </p>
              </div>
              <Separator className="w-full" />

              <div className="space-y-4 p-4">
                <div className="flex items-center justify-between">
                  <span className="flex items-center font-[13px]">
                    OpenAI API key
                    <span className="ml-1 text-destructive">*</span>
                    <IconComponent
                      name="Info"
                      strokeWidth={ICON_STROKE_WIDTH}
                      className="relative left-1 top-[1px] h-4 w-4 text-placeholder"
                    />
                  </span>
                </div>

                <InputGlobalComponent
                  value={apiKey}
                  placeholder="Enter a token..."
                  id="global_variable_to_transcribe"
                  editNode={false}
                  disabled={false}
                  handleOnNewValue={(changes) => {
                    setApiKey(changes.value);
                  }}
                  load_from_db={true}
                  password={false}
                  display_name="OpenAI API key"
                />

                <Button
                  onClick={handleSubmit}
                  disabled={!apiKey.trim()}
                  className="w-full bg-primary"
                >
                  Start Transcribing
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default ApiKeyPopup;
