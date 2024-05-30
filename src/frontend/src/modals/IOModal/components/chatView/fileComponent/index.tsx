import * as base64js from "base64-js";
import { useState } from "react";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../../components/genericIconComponent";
import { fileCardPropsType } from "../../../../../types/components";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import { BACKEND_URL, BASE_URL_API } from "../../../../../constants/constants";
import formatFileName from "../filePreviewChat/utils/format-file-name";

const imgTypes = new Set(["png", "jpg"]);

export default function FileCard({
  fileName,
  content,
  fileType,
  showFile = true,
}: fileCardPropsType): JSX.Element | undefined {
  const handleDownload = async (): Promise<void> => {
    try {
      const response = await fetch(
        `${BACKEND_URL.slice(0, BACKEND_URL.length - 1)}${BASE_URL_API}files/download/${content}`,
      );
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);

      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", fileName); // Set the filename
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      URL.revokeObjectURL(url); // Clean up the URL object
    } catch (error) {
      console.error("Failed to download file:", error);
    }
  };
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
            {isHovered && (
              <div
                className={`absolute right-1 top-1 rounded-bl-lg bg-muted text-sm font-bold text-foreground `}
              >
                <button
                  className="px-2 py-1 text-ring "
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
        </div>
      );
    }

    return (
      <div
        className={`relative ${false ? "h-20 w-20" : "h-20 w-80"} cursor-pointer rounded-lg border  border-ring bg-muted shadow transition duration-300 hover:drop-shadow-lg ${
          isHovered ? "shadow-md" : ""
        }`}
        onClick={handleDownload}
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
        {isHovered && (
          <div
            className={`absolute right-0 top-1 rounded-bl-lg bg-muted px-1 text-sm font-bold text-foreground `}
          >
            <button className="px-2 py-1 text-ring " onClick={handleDownload}>
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
  return undefined;
}
