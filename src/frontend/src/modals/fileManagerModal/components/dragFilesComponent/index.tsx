import ShadTooltip from "@/components/common/shadTooltipComponent";
import useUploadFile from "@/hooks/files/use-upload-file";
import useAlertStore from "@/stores/alertStore";
import { useUtilityStore } from "@/stores/utilityStore";
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
  const image = `url("data:image/svg+xml,%3Csvg width='100%25' height='100%25' xmlns='http://www.w3.org/2000/svg'%3E%3Crect width='100%25' height='100%25' fill='none' rx='16' ry='16' stroke='%23FFFFFF' stroke-width='2px' stroke-dasharray='5%2c 5' stroke-dashoffset='0' stroke-linecap='butt'/%3E%3C/svg%3E")`;
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
        onUpload(filesIds);
        setSuccessData({
          title: `File${filesIds.length > 1 ? "s" : ""} uploaded successfully`,
        });
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
      onUpload(filesIds);
      setSuccessData({
        title: `File${filesIds.length > 1 ? "s" : ""} uploaded successfully`,
      });
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
        <p className="flex items-center gap-1 text-xs text-muted-foreground">
          <span>{types.slice(0, 3).join(", ")}</span>
          {types.length > 3 && (
            <ShadTooltip content={types.slice(3).join(", ")}>
              <span className="cursor-help text-accent-pink-foreground underline">
                +{types.length - 3} more
              </span>
            </ShadTooltip>
          )}
          <span className="font-semibold">
            {maxFileSizeUpload / 1024 / 1024} MB
          </span>
          <span>max</span>
        </p>
        <div
          className="pointer-events-none absolute h-full w-full rounded-2xl bg-placeholder-foreground"
          style={{
            WebkitMaskImage: image,
            maskImage: image,
          }}
        />
      </div>
    </div>
  );
}
