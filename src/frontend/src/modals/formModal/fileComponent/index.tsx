import * as base64js from "base64-js";
import { useState } from "react";
import { DownloadCloud, File } from "lucide-react";

export default function FileCard({ fileName, content, fileType }) {
  const handleDownload = () => {
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
  function handleMouseEnter() {
    setIsHovered(true);
  }
  function handleMouseLeave() {
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
          <div
            className={`absolute right-0 top-0 rounded-bl-lg bg-muted px-1 text-sm font-bold text-foreground `}
          >
            <button className="px-2 py-1 text-ring " onClick={handleDownload}>
              <DownloadCloud className="h-5 w-5 text-current hover:scale-110" />
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <button
      onClick={handleDownload}
      className="flex w-1/2 items-center justify-between rounded border border-ring bg-muted px-2 py-2 text-foreground shadow hover:drop-shadow-lg"
    >
      <div className="mr-2 flex w-full items-center gap-2 text-current">
        {" "}
        {fileType === "image" ? (
          <img
            src={`data:image/png;base64,${content}`}
            alt=""
            className="h-8 w-8"
          />
        ) : (
          <File className="h-8 w-8" />
        )}
        <div className="flex flex-col items-start">
          {" "}
          <div className="truncate text-sm text-current">{fileName}</div>
          <div className="truncate text-xs  text-ring">{fileType}</div>
        </div>
        <DownloadCloud className="ml-auto h-6 w-6 text-current" />
      </div>
    </button>
  );
}
