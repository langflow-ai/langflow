import ForwardedIconComponent from "../../../../../../../components/genericIconComponent";

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
      <button
        className="font-bold text-white transition-all hover:text-muted-foreground"
        onClick={handleButtonClick}
      >
        <ForwardedIconComponent name="PaperclipIcon" />
      </button>
    </div>
  );
};

export default UploadFileButton;
