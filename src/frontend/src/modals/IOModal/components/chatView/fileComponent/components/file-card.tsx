import { useState } from "react";
import { useGetDownloadFileMutation } from "@/controllers/API/queries/files";
import { getBaseUrl } from "@/customization/utils/urls";
import { ForwardedIconComponent } from "../../../../../../components/common/genericIconComponent";
import type { fileCardPropsType } from "../../../../../../types/components";
import formatFileName from "../utils/format-file-name";
import getClasses from "../utils/get-classes";
import DownloadButton from "./download-button";
import CustomAuthenticatedImage from "@/customization/components/custom-authenticated-image";

const imgTypes = new Set(["png", "jpg", "jpeg", "gif", "webp", "image"]);

/**
 * Determines if a file is an image based on type or path extension
 */
function isImageFile(fileType: string | undefined, path: string): boolean {
  // First check the fileType directly
  if (fileType && imgTypes.has(fileType.toLowerCase())) {
    return true;
  }
  // If fileType is generic (like "file") or undefined, extract extension from path
  const extension = path.split(".").pop()?.toLowerCase() || "";
  return imgTypes.has(extension);
}

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

  const imgSrc = `${getBaseUrl()}files/images/${path}`;

  if (showFile) {
    if (isImageFile(fileType, path)) {
      return (
        <div
          className="inline-block w-full rounded-lg transition-all"
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          style={{ display: "inline-block" }}
        >
          <div className="relative w-[50%] rounded-lg border border-border">
            <CustomAuthenticatedImage
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
