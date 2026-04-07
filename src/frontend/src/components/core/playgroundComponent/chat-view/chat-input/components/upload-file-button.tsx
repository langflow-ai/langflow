import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import {
  CHAT_UPLOAD_ATTACHMENT_ACCEPT,
  CHAT_UPLOAD_ATTACHMENT_TOOLTIP,
} from "@/constants/file-upload-constants";
import { Button } from "@/components/ui/button";

interface UploadFileButtonProps {
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  handleFileChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  handleButtonClick: () => void;
  isBuilding: boolean;
}

const UploadFileButton = ({
  fileInputRef,
  handleFileChange,
  handleButtonClick,
  isBuilding,
}: UploadFileButtonProps) => {
  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    handleButtonClick();
  };

  return (
    <ShadTooltip
      styleClasses="z-50"
      side="right"
      content={CHAT_UPLOAD_ATTACHMENT_TOOLTIP}
    >
      <div>
        <input
          disabled={isBuilding}
          type="file"
          ref={fileInputRef}
          style={{ display: "none" }}
          onChange={handleFileChange}
          accept={CHAT_UPLOAD_ATTACHMENT_ACCEPT}
        />
        <Button
          disabled={isBuilding}
          className={`h-7 w-7 px-0 flex items-center justify-center ${
            isBuilding
              ? "cursor-not-allowed"
              : "text-muted-foreground hover:text-primary"
          }`}
          onClick={handleClick}
          unstyled
        >
          <ForwardedIconComponent className="h-[18px] w-[18px]" name="File" />
        </Button>
      </div>
    </ShadTooltip>
  );
};

export default UploadFileButton;
