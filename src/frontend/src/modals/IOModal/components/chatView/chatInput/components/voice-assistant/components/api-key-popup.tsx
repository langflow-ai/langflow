import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import InputGlobalComponent from "@/components/core/parameterRenderComponent/components/inputGlobalComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { FC, useEffect, useRef, useState } from "react";

interface ApiKeyPopUpProps {
  onSubmit: (apiKey: string) => void;
  onClose?: () => void;
  isOpen: boolean;
  hasMessage?: string;
  children: React.ReactNode;
}

const ApiKeyPopUp = ({
  onSubmit,
  onClose,
  isOpen,
  hasMessage,
  children,
}: ApiKeyPopUpProps) => {
  const [apiKey, setApiKey] = useState<string>("");
  const popupRef = useRef<HTMLDivElement>(null);

  const handleSubmit = () => {
    onSubmit(apiKey);
  };

  return (
    <>
      <DropdownMenu open={isOpen}>
        <DropdownMenuTrigger>{children}</DropdownMenuTrigger>
        <DropdownMenuContent>
          <div ref={popupRef}>
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
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
};

export default ApiKeyPopUp;
