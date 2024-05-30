import * as base64js from "base64-js";
import { useState } from "react";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../../components/genericIconComponent";
import { fileCardPropsType } from "../../../../../types/components";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import { BACKEND_URL, BASE_URL_API } from "../../../../../constants/constants";
import formatFileName from "../filePreviewChat/utils/format-file-name";
import DownloadButton from "./components/downloadButton/downloadButton";
import handleDownload from "./utils/handle-download";

const imgTypes = new Set(["png", "jpg"]);

export default function FileCard({
  fileName,
  content,
  fileType,
  showFile = true,
}: fileCardPropsType): JSX.Element | undefined {
  const [isHovered, setIsHovered] = useState(false);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  function handleMouseEnter(): void {
    setIsHovered(true);
  }
  function handleMouseLeave(): void {
    setIsHovered(false);
  }

  const imgSrc = `${BACKEND_URL.slice(0, BACKEND_URL.length - 1)}${BASE_URL_API}files/images/${content}`;

  if (showFile) {
    if (imgTypes.has(fileType)) {
      return (
        <div
          className="inline-block w-full rounded-lg transition-all"
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          style={{ display: "inline-block" }}
        >
          <div className="relative w-[50%] rounded-lg border border-border">
            <img
              src={imgSrc}
              alt="generated image"
              className="m-0  h-auto w-auto rounded-lg border border-border p-0 transition-all"
            />
            <DownloadButton
              isHovered={isHovered}
              handleDownload={() => handleDownload({ fileName, content })}
            />
          </div>
        </div>
      );
    }

    return (
      <div
        className={`relative ${false ? "h-20 w-20" : "h-20 w-80"} cursor-pointer rounded-lg border  border-ring bg-muted shadow transition duration-300 hover:drop-shadow-lg ${
          isHovered ? "shadow-md" : ""
        }`}
        onClick={() => handleDownload({ fileName, content })}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        <div className="ml-3 flex h-full w-full items-center gap-2 text-sm">
          <ForwardedIconComponent name="File" className="h-8 w-8" />
          <div className="flex flex-col">
            <span className="font-bold">{formatFileName(fileName, 20)}</span>
            <span>File</span>
          </div>
        </div>
        <DownloadButton
          isHovered={isHovered}
          handleDownload={() => handleDownload({ fileName, content })}
        />
      </div>
    );
  }
  return undefined;
}
