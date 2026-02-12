import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import type { FilePreviewType } from "@/types/components";
import { cn } from "@/utils/utils";

const BUTTON_STATES = {
  NO_INPUT: "bg-high-indigo text-background",
  DEFAULT:
    "bg-primary text-primary-foreground hover:bg-primary-hover hover:text-secondary",
  BUILDING:
    "bg-muted text-foreground hover:bg-secondary-hover dark:hover:bg-input",
};

type ButtonSendWrapperProps = {
  send: () => void;
  noInput: boolean;
  chatValue: string;
  files: FilePreviewType[];
  isBuilding: boolean;
  stopBuilding: () => void;
};

const ButtonSendWrapper = ({
  send,
  noInput,
  chatValue,
  files,
  isBuilding,
  stopBuilding,
}: ButtonSendWrapperProps) => {
  const isLoading = files.some((file) => file.loading);

  const getButtonState = () => {
    if (isBuilding) return BUTTON_STATES.BUILDING;
    if (noInput) return BUTTON_STATES.NO_INPUT;
    return BUTTON_STATES.DEFAULT;
  };

  const buttonClasses = cn("form-modal-send-button", getButtonState());

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    if (isBuilding) {
      stopBuilding();
      return;
    }
    if (!isLoading) {
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
      disabled={isLoading && !isBuilding}
      unstyled
      data-testid={isBuilding ? "button-stop" : "button-send"}
      aria-label={isBuilding ? "Stop" : "Send"}
    >
      <div className="flex h-fit w-fit items-center gap-2 text-sm font-medium">
        <ForwardedIconComponent
          name={isBuilding ? "Square" : "ArrowUp"}
          className={cn("h-4 w-4", isBuilding && "h-3 w-3")}
        />
      </div>
    </Button>
  );
};

export default ButtonSendWrapper;
