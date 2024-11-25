import { useGetDownloadFileMutation } from "@/controllers/API/queries/files";
import { useState } from "react";
import { ForwardedIconComponent } from "../../../../../components/common/genericIconComponent";
import { BASE_URL_API } from "../../../../../constants/constants";
import { fileCardPropsType } from "../../../../../types/components";
import formatFileName from "../filePreviewChat/utils/format-file-name";
import DownloadButton from "./components/downloadButton/downloadButton";
import getClasses from "./utils/get-classes";

const imgTypes = new Set(["png", "jpg", "jpeg", "gif", "webp", "image"]);

export default function FileCard({
  fileName,
  path,
  fileType,
  showFile = true,
}: fileCardPropsType): JSX.Element | undefined {
  const [isHovered, setIsHovered] = useState(false);
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

  const fileWrapperClasses = getClasses(isHovered);

  const imgSrc = `${BASE_URL_API}files/images/${path}`;

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
