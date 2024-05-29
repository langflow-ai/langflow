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
        className="absolute rounded bg-blue-500 px-4 py-2 font-bold text-white hover:bg-blue-700"
        onClick={handleButtonClick}
      >
        Upload File
      </button>
    </div>
  );
};

export default UploadFileButton;
