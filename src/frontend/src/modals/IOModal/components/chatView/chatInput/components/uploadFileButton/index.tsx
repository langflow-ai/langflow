import ForwardedIconComponent from "../../../../../../../components/genericIconComponent";
import { Button } from "../../../../../../../components/ui/button";

const UploadFileButton = ({
  fileInputRef,
  handleFileChange,
  handleButtonClick,
}) => {
  return (
    <div>
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: "none" }}
        onChange={handleFileChange}
      />
      <Button
        className="font-bold text-white transition-all hover:text-muted-foreground"
        onClick={handleButtonClick}
        variant="none"
        size="none"
      >
        <ForwardedIconComponent name="PaperclipIcon" />
      </Button>
    </div>
  );
};

export default UploadFileButton;
