import * as base64js from "base64-js";
import { useState } from "react";
import IconComponent from "../../../../../components/genericIconComponent";
import { fileCardPropsType } from "../../../../../types/components";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import { BACKEND_URL, BASE_URL_API } from "../../../../../constants/constants";

const imgTypes = new Set(["png", "jpg"]);

export default function FileCard({
  fileName,
  content,
  fileType,
}: fileCardPropsType): JSX.Element {
  const handleDownload = (): void => {
    //TODO: update download function
  };
  const [isHovered, setIsHovered] = useState(false);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  function handleMouseEnter(): void {
    setIsHovered(true);
  }
  function handleMouseLeave(): void {
    setIsHovered(false);
  }

  if (imgTypes.has(fileType)) {
    return (
      <div
        className="relative h-1/4 w-1/4"
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        <img
            src={`${BACKEND_URL.slice(0,BACKEND_URL.length-1)}${BASE_URL_API}files/images/${content}`}
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
        {" "}
        {imgTypes.has(fileType) ? (
          <img
            src={`${BACKEND_URL.slice(0,BACKEND_URL.length-1)}${BASE_URL_API}files/images/${content}`}
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
