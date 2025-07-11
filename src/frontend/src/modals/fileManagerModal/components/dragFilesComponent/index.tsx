import ShadTooltip from "@/components/common/shadTooltipComponent";
import useUploadFile from "@/hooks/files/use-upload-file";
import useAlertStore from "@/stores/alertStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { formatFileSize } from "@/utils/stringManipulation";
import { useState } from "react";

export default function DragFilesComponent({
  onUpload,
  types,
  isList,
}: {
  onUpload: (filesPaths: string[]) => void;
  types: string[];
  isList: boolean;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const uploadFile = useUploadFile({
    types,
    multiple: isList,
  });
  const maxFileSizeUpload = useUtilityStore((state) => state.maxFileSizeUpload);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.types.some((type) => type === "Files")) {
      setIsDragging(true);
    }
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.types.some((type) => type === "Files")) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    if (droppedFiles.length > 0) {
      try {
        const filesIds = await uploadFile({
          files: droppedFiles,
        });
        if (filesIds.length > 0) {
          onUpload(filesIds);
          setSuccessData({
            title: `File${filesIds.length > 1 ? "s" : ""} uploaded successfully`,
          });
        }
      } catch (error: any) {
        setErrorData({
          title: "Error uploading file",
          list: [error.message || "An error occurred while uploading the file"],
        });
      }
    }
  };

  const handleClick = async () => {
    try {
      const filesIds = await uploadFile({});
      if (filesIds.length > 0) {
        onUpload(filesIds);
        setSuccessData({
          title: `File${filesIds.length > 1 ? "s" : ""} uploaded successfully`,
        });
      }
    } catch (error: any) {
      setErrorData({
        title: "Error uploading file",
        list: [error.message || "An error occurred while uploading the file"],
      });
    }
  };

  return (
    <div className="flex flex-col items-center justify-center">
      <div
        className={`relative flex h-full w-full cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl p-8 transition-colors ${
          isDragging ? "bg-accent-foreground/10" : ""
        }`}
        onDragOver={handleDragOver}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        data-testid="drag-files-component"
        role="button"
        tabIndex={0}
      >
        <h3 className="text-sm font-semibold">
          {isDragging ? "Drop files here" : "Click or drag files here"}
        </h3>
        <p className="text-muted-foreground flex items-center gap-1 text-xs">
          <span>{types.slice(0, 3).join(", ")}</span>
          {types.length > 3 && (
            <ShadTooltip content={types.slice(3).join(", ")}>
              <span className="text-accent-pink-foreground underline">
                +{types.length - 3} more
              </span>
            </ShadTooltip>
          )}
          <span className="font-semibold">
            {formatFileSize(maxFileSizeUpload)}
          </span>
          <span>max</span>
        </p>
        <div className="pointer-events-none absolute inset-0 h-full w-full">
          <svg
            width="100%"
            height="100%"
            className="stroke-muted-foreground/50 overflow-visible"
            style={{
              position: "absolute",
              top: 1,
              left: 1,
              right: 0,
              bottom: 0,
            }}
          >
            <rect
              width="99.5%"
              height="99.5%"
              fill="none"
              rx="16"
              ry="16"
              strokeWidth="1"
              strokeDasharray="5,5"
              strokeDashoffset="0"
              strokeLinecap="butt"
            />
          </svg>
        </div>
      </div>
    </div>
  );
}
