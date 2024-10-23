import Loading from "@/components/ui/loading";
import useFlowStore from "@/stores/flowStore";
import IconComponent from "../../../../../../../components/genericIconComponent";
import { Button } from "../../../../../../../components/ui/button";
import { Case } from "../../../../../../../shared/components/caseComponent";
import { FilePreviewType } from "../../../../../../../types/components";
import { classNames } from "../../../../../../../utils/utils";

const BUTTON_STATES = {
  NO_INPUT: "bg-high-indigo text-background",
  HAS_CHAT_VALUE: "text-primary",
  SHOW_STOP: "bg-zinc-400 text-white cursor-pointer",
  DEFAULT: "bg-chat-send text-background",
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
    >
      <Case condition={showStopButton}>
        <div className="flex items-center gap-2">
          Stop
          <Loading className="text-black" />
        </div>
      </Case>

      <Case condition={showPlayButton}>
        <IconComponent
          name="Zap"
          className="form-modal-play-icon"
          aria-hidden="true"
        />
      </Case>

      <Case condition={showSendButton}>
        <div className="flex items-center gap-2">Send</div>
      </Case>
    </Button>
  );
};

export default ButtonSendWrapper;
