import Loading from "@/components/ui/loading";
import useFlowStore from "@/stores/flowStore";
import { Button } from "../../../../../../components/ui/button";
import { Case } from "../../../../../../shared/components/caseComponent";
import { FilePreviewType } from "../../../../../../types/components";
import { classNames } from "../../../../../../utils/utils";

const BUTTON_STATES = {
  NO_INPUT: "bg-high-indigo text-background",
  HAS_CHAT_VALUE: "text-primary",
  SHOW_STOP:
    "bg-muted hover:bg-secondary-hover dark:hover:bg-input text-foreground cursor-pointer",
  DEFAULT:
    "bg-primary text-primary-foreground hover:bg-primary-hover hover:text-secondary",
};

type ButtonSendWrapperProps = {
  send: () => void;
  lockChat: boolean;
  noInput: boolean;
  chatValue: string;
  files: FilePreviewType[];
};

const ButtonSendWrapper = ({
  send,
  lockChat,
  noInput,
  chatValue,
  files,
}: ButtonSendWrapperProps) => {
  const stopBuilding = useFlowStore((state) => state.stopBuilding);

  const isBuilding = useFlowStore((state) => state.isBuilding);
  const showStopButton = lockChat || files.some((file) => file.loading);
  const showPlayButton = !lockChat && noInput;
  const showSendButton =
    !(lockChat || files.some((file) => file.loading)) && !noInput;

  const getButtonState = () => {
    if (showStopButton) return BUTTON_STATES.SHOW_STOP;
    if (noInput) return BUTTON_STATES.NO_INPUT;
    if (chatValue) return BUTTON_STATES.DEFAULT;

    return BUTTON_STATES.DEFAULT;
  };

  const buttonClasses = classNames("form-modal-send-button", getButtonState());

  const handleClick = () => {
    if (showStopButton && isBuilding) {
      stopBuilding();
    } else if (!showStopButton) {
      send();
    }
  };

  return (
    <Button
      className={buttonClasses}
      disabled={lockChat && !isBuilding}
      onClick={handleClick}
      unstyled
      data-testid={showStopButton ? "button-stop" : "button-send"}
    >
      <Case condition={showStopButton}>
        <div className="flex items-center gap-2 rounded-md text-[14px] font-medium">
          Stop
          <Loading className="h-[16px] w-[16px]" />
        </div>
      </Case>

      {/* <Case condition={showPlayButton}>
        <IconComponent
          name="Zap"
          className="form-modal-play-icon"
          aria-hidden="true"
        />
      </Case> */}

      <Case condition={showSendButton}>
        <div className="flex h-fit w-fit items-center gap-2 text-[14px] font-medium">
          Send
        </div>
      </Case>
    </Button>
  );
};

export default ButtonSendWrapper;
