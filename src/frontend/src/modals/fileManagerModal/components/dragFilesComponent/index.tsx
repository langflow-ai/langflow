import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Switch } from "@/components/ui/switch";
import useUploadFile from "@/hooks/files/use-upload-file";
import useAlertStore from "@/stores/alertStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { formatFileSize } from "@/utils/stringManipulation";

export default function DragFilesComponent({
  onUpload,
  types,
  isList,
  allowFolderSelection = false,
}: {
  onUpload: (filesPaths: string[]) => void;
  types: string[];
  isList: boolean;
  allowFolderSelection?: boolean;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [isFolderMode, setIsFolderMode] = useState(false);
  const uploadFile = useUploadFile({
    types,
    multiple: isList || isFolderMode,
    webkitdirectory: isFolderMode,
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
            title: `File${
              filesIds.length > 1 ? "s" : ""
            } uploaded successfully`,
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
      {allowFolderSelection && (
        <div className="flex items-center justify-center gap-3 mb-4 p-2 rounded-lg border border-border">
          <div className="flex items-center gap-2">
            <ForwardedIconComponent name="File" className="h-4 w-4" />
            <span className="text-sm font-medium">Files</span>
          </div>
          <Switch
            checked={isFolderMode}
            onCheckedChange={setIsFolderMode}
            className="data-[state=checked]:bg-primary"
          />
          <div className="flex items-center gap-2">
            <ForwardedIconComponent name="Folder" className="h-4 w-4" />
            <span className="text-sm font-medium">Folder</span>
          </div>
        </div>
      )}
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
          {isDragging
            ? isFolderMode
              ? "Drop folder here"
              : "Drop files here"
            : isFolderMode
              ? "Click to select a folder"
              : "Click or drag files here"}
        </h3>
        {isFolderMode && (
          <div className="text-xs text-muted-foreground text-center max-w-md space-y-1">
            <p>
              Select a folder to upload all supported files from that folder
            </p>
            <p className="text-amber-600 dark:text-amber-400 font-medium">
              ⚠️ Avoid folders with large hidden directories (.mypy_cache, .git,
              node_modules, etc.)
            </p>
          </div>
        )}
        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <span>{types.slice(0, 3).join(", ")}</span>
            {types.length > 3 && (
              <ShadTooltip content={types.slice(3).toSorted().join(", ")}>
                <span
                  className="text-muted-foreground flex items-center gap-1"
                  data-testid="info-types"
                >
                  +{types.length - 3} more
                  <ForwardedIconComponent name="info" className="w-3 h-3" />
                </span>
              </ShadTooltip>
            )}
          </div>
          <span className="font-semibold">
            {formatFileSize(maxFileSizeUpload)} max
          </span>
        </p>
        <div className="pointer-events-none absolute inset-0 h-full w-full">
          <svg
            width="100%"
            height="100%"
            className="overflow-visible stroke-muted-foreground/50"
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
