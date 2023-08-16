import * as base64js from "base64-js";
import { useState } from "react";
import IconComponent from "../../../components/genericIconComponent";
import { fileCardPropsType } from "../../../types/components";

export default function FileCard({
  fileName,
  content,
  fileType,
}: fileCardPropsType): JSX.Element {
  const handleDownload = (): void => {
    const byteArray = new Uint8Array(base64js.toByteArray(content));
    const blob = new Blob([byteArray], { type: "application/octet-stream" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName + ".png";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };
  const [isHovered, setIsHovered] = useState(false);
  function handleMouseEnter(): void {
    setIsHovered(true);
  }
  function handleMouseLeave(): void {
    setIsHovered(false);
  }

  if (fileType === "image") {
    return (
      <div
        className="relative h-1/4 w-1/4"
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        <img
          src={`data:image/png;base64,${content}`}
          alt="generated image"
          className="h-full  w-full rounded-lg"
        />
        {isHovered && (
          <div className={`file-card-modal-image-div `}>
            <button
              className="file-card-modal-image-button "
              onClick={handleDownload}
            >
              <IconComponent
                name="DownloadCloud"
                className="h-5 w-5 text-current hover:scale-110"
              />
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <button onClick={handleDownload} className="file-card-modal-button">
      <div className="file-card-modal-div">
        ooooooooooooooo{" "}
        {fileType === "image" ? (
          <img
            src={`data:image/png;base64,${content}`}
            alt=""
            className="h-8 w-8"
          />
        ) : (
          <IconComponent name="File" className="h-8 w-8" />
        )}
        <div className="file-card-modal-footer">
          {" "}
          <div className="file-card-modal-name">{fileName}</div>
          <div className="file-card-modal-type">{fileType}</div>
        </div>
        <IconComponent
          name="DownloadCloud"
          className="ml-auto h-6 w-6 text-current"
        />
      </div>
    </button>
  );
}
