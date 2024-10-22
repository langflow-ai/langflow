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
        className={`rounded-md bg-zinc-500 p-1 font-bold transition-all ${
          lockChat ? "cursor-not-allowed" : "hover:text-muted-foreground"
        }`}
        onClick={handleButtonClick}
        unstyled
      >
        <ForwardedIconComponent name="Image" />
      </Button>
    </div>
  );
};

export default UploadFileButton;
