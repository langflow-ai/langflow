import ShadTooltip from "@/components/common/shadTooltipComponent";
import {
  CHAT_ATTACHMENT_UPLOAD_ACCEPT,
  CHAT_ATTACHMENT_UPLOAD_TOOLTIP,
} from "@/constants/constants";
import ForwardedIconComponent from "../../../../../../components/common/genericIconComponent";
import { Button } from "../../../../../../components/ui/button";

const UploadFileButton = ({
  fileInputRef,
  handleFileChange,
  handleButtonClick,
  isBuilding,
}) => {
  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    handleButtonClick();
  };

  return (
    <ShadTooltip
      styleClasses="z-50"
      side="right"
      content={CHAT_ATTACHMENT_UPLOAD_TOOLTIP}
    >
      <div>
        <input
          disabled={isBuilding}
          type="file"
          ref={fileInputRef}
          style={{ display: "none" }}
          onChange={handleFileChange}
          accept={CHAT_ATTACHMENT_UPLOAD_ACCEPT}
        />
        <Button
          disabled={isBuilding}
          className={`btn-playground-actions ${
            isBuilding
              ? "cursor-not-allowed"
              : "text-muted-foreground hover:text-primary"
          }`}
          onClick={handleClick}
          unstyled
        >
          <ForwardedIconComponent name="File" />
        </Button>
      </div>
    </ShadTooltip>
  );
};

export default UploadFileButton;
