import ShadTooltip from "@/components/common/shadTooltipComponent";
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
      content="Attach file (png, jpg, jpeg, gif, pdf, audio)"
    >
      <div>
        <input
          disabled={isBuilding}
          type="file"
          ref={fileInputRef}
          style={{ display: "none" }}
          accept="image/png,image/jpeg,image/jpg,image/gif,application/pdf,audio/*,.mp3,.wav,.m4a,.ogg,.webm"
          onChange={handleFileChange}
        />
        <Button
          disabled={isBuilding}
          className={`btn-playground-actions ${isBuilding
              ? "cursor-not-allowed"
              : "text-muted-foreground hover:text-primary"
            }`}
          onClick={handleClick}
          unstyled
        >
          <ForwardedIconComponent className="h-[18px] w-[18px]" name="Paperclip" />
        </Button>
      </div>
    </ShadTooltip>
  );
};

export default UploadFileButton;
