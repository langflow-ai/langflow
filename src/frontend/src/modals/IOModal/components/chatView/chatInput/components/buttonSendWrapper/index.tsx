import IconComponent from "../../../../../../../components/genericIconComponent";
import { Case } from "../../../../../../../shared/components/caseComponent";
import { FilePreviewType } from "../../../../../../../types/components";
import { classNames } from "../../../../../../../utils/utils";

type ButtonSendWrapperProps = {
  send: () => void;
  lockChat: boolean;
  noInput: boolean;
  saveLoading: boolean;
  chatValue: string;
  files: FilePreviewType[];
};

const ButtonSendWrapper = ({
  send,
  lockChat,
  noInput,
  saveLoading,
  chatValue,
  files,
}: ButtonSendWrapperProps) => {
  return (
    <button
      className={classNames(
        "form-modal-send-button",
        noInput
          ? "bg-high-indigo text-background"
          : chatValue === ""
            ? "text-primary"
            : "bg-chat-send text-background",
      )}
      disabled={lockChat || saveLoading}
      onClick={(): void => send()}
    >
      <Case
        condition={
          lockChat || saveLoading || files.some((file) => file.loading)
        }
      >
        <IconComponent
          name="Lock"
          className="form-modal-lock-icon"
          aria-hidden="true"
        />
      </Case>

      <Case condition={noInput}>
        <IconComponent
          name="Zap"
          className="form-modal-play-icon"
          aria-hidden="true"
        />
      </Case>

      <Case
        condition={
          !(lockChat || saveLoading || files.some((file) => file.loading)) &&
          !noInput
        }
      >
        <IconComponent
          name="LucideSend"
          className="form-modal-send-icon "
          aria-hidden="true"
        />
      </Case>
    </button>
  );
};

export default ButtonSendWrapper;
