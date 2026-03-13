import { Square } from "lucide-react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import useFlowStore from "@/stores/flowStore";
import type { FilePreviewType } from "@/types/components";
import { cn } from "@/utils/utils";

const BUTTON_STATES = {
  NO_INPUT: "bg-high-indigo text-background",
  DEFAULT:
    "bg-primary text-primary-foreground hover:bg-primary-hover hover:text-secondary",
};

type ButtonSendWrapperProps = {
  send: () => void;
  noInput: boolean;
  chatValue: string;
  files: FilePreviewType[];
  isBuilding?: boolean;
};

const ButtonSendWrapper = ({
  send,
  noInput,
  files,
  isBuilding,
}: ButtonSendWrapperProps) => {
  const stopBuilding = useFlowStore((state) => state.stopBuilding);
  const isLoading = files.some((file) => file.loading);

  const getButtonState = () => {
    if (noInput) return BUTTON_STATES.NO_INPUT;
    return BUTTON_STATES.DEFAULT;
  };

  const buttonClasses = cn("form-modal-send-button", getButtonState());

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();

    if (isBuilding) {
      stopBuilding();
    } else if (!isLoading) {
      send();
    }
  };

  return (
    <Button
      className={cn(
        buttonClasses,
        "h-6 w-6 px-0 flex items-center justify-center",
      )}
      onClick={handleClick}
      disabled={isLoading}
      unstyled
      data-testid="button-send"
      title={isBuilding ? "Cancel" : "Send"}
    >
      <div className="flex h-fit w-fit items-center gap-2 text-sm font-medium">
        {isBuilding ? (
          <Square className="h-3.5 w-3.5" fill="currentColor" />
        ) : (
          <ForwardedIconComponent name="ArrowUp" className="h-4 w-4" />
        )}
      </div>
    </Button>
  );
};

export default ButtonSendWrapper;
