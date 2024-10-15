import ForwardedIconComponent from "../../../../../../../components/genericIconComponent";
import { Button } from "../../../../../../../components/ui/button";

const UploadFileButton = ({
  fileInputRef,
  handleFileChange,
  handleButtonClick,
  lockChat,
}) => {
  return (
    <div>
      <input
        disabled={lockChat}
        type="file"
        ref={fileInputRef}
        style={{ display: "none" }}
        onChange={handleFileChange}
      />
      <Button
        disabled={lockChat}
        className={`font-bold transition-all dark:text-white ${
          lockChat ? "cursor-not-allowed" : "hover:text-muted-foreground"
        }`}
        onClick={handleButtonClick}
        unstyled
      >
        <ForwardedIconComponent name="PaperclipIcon" />
      </Button>
    </div>
  );
};

export default UploadFileButton;
