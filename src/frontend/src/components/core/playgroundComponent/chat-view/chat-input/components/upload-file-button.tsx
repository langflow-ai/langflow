import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";

interface UploadFileButtonProps {
  fileInputRef: React.RefObject<HTMLInputElement>;
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
      content="Attach image (png, jpg, jpeg)"
    >
      <div>
        <input
          disabled={isBuilding}
          type="file"
          ref={fileInputRef}
          style={{ display: "none" }}
          onChange={handleFileChange}
          accept=".png,.jpg,.jpeg,image/png,image/jpeg"
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
          <ForwardedIconComponent className="h-[18px] w-[18px]" name="Image" />
        </Button>
      </div>
    </ShadTooltip>
  );
};

export default UploadFileButton;
