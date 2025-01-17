import { useGetDownloadFileMutation } from "@/controllers/API/queries/files";
import { useState } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { usePlaygroundStore } from "src/stores/playgroundStore";
import formatFileName from "src/utils/strings";
import { fileCardPropsType } from "./types";
import DownloadButton from "../DownloadButton/download-button";

const imgTypes = new Set(["png", "jpg", "jpeg", "gif", "webp", "image"]);

export default function FileCard({
  fileName,
  path,
  fileType,
  showFile = true,
}: fileCardPropsType): JSX.Element | undefined {
  const [isHovered, setIsHovered] = useState(false);
  const { baseUrl } = usePlaygroundStore();
  const { mutate } = useGetDownloadFileMutation({
    filename: fileName,
    path: path,
  });
  function handleMouseEnter(): void {
    setIsHovered(true);
  }
  function handleMouseLeave(): void {
    setIsHovered(false);
  }

  function getClasses(isHovered: boolean): string {
    return `relative cursor-pointer rounded-lg border h-20 w-80 border-ring bg-muted shadow transition duration-300 hover:drop-shadow-lg ${
      isHovered ? "shadow-md" : ""
    }`;
  }

  const fileWrapperClasses = getClasses(isHovered);

  const imgSrc = `${baseUrl}files/images/${path}`;

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
              className="m-0 h-auto w-auto rounded-lg border border-border p-0 transition-all"
            />
            <DownloadButton
              isHovered={isHovered}
              handleDownload={() => mutate(undefined)}
            />
          </div>
        </div>
      );
    }

    return (
      <div
        className={fileWrapperClasses}
        onClick={() => mutate(undefined)}
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
          handleDownload={() => mutate(undefined)}
        />
      </div>
    );
  }
  return undefined;
}
