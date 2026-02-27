import { useMemo, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { createFileUpload } from "@/helpers/create-file-upload";
import useUploadFile from "@/hooks/files/use-upload-file";
import useAlertStore from "@/stores/alertStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { FileType } from "@/types/file_management";
import { getRelativePathForServerPath } from "@/utils/file-relative-path-map";
import { formatFileSize } from "@/utils/stringManipulation";

import {
  dedupeFolderRootIfNeeded,
  filterFilesByTypes,
  filterHiddenAndIgnoredFolderFiles,
  getDroppedFilesFromDragEvent,
  getRootFolderFromRelativePath,
} from "./helpers";

export default function DragFilesComponent({
  onUpload,
  types,
  isList,
  allowFolderSelection = false,
  existingFiles,
}: {
  onUpload: (filesPaths: string[]) => void;
  types: string[];
  isList: boolean;
  allowFolderSelection?: boolean;
  existingFiles?: FileType[];
}) {
  const [isDragging, setIsDragging] = useState(false);

  const sessionUsedFolderRootsRef = useRef<Set<string>>(new Set());

  const existingFolderRoots = useMemo(() => {
    const roots = new Set<string>();
    for (const file of existingFiles ?? []) {
      const relativePath =
        getRelativePathForServerPath(file.path) ??
        file.file?.webkitRelativePath;
      const root = getRootFolderFromRelativePath(relativePath);
      if (root) roots.add(root);
    }
    return roots;
  }, [existingFiles]);
  const uploadFiles = useUploadFile({
    types,
    multiple: isList,
    webkitdirectory: false,
  });
  const uploadFolder = useUploadFile({
    types,
    multiple: true,
    webkitdirectory: true,
  });
  const maxFileSizeUpload = useUtilityStore((state) => state.maxFileSizeUpload);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const shouldTreatDropAsFolder = (args: {
    hasDirectories: boolean;
    files: File[];
  }) => {
    if (!allowFolderSelection) return false;
    if (args.hasDirectories) return true;
    // Some browsers may not flag hasDirectories but still provide webkitRelativePath.
    return args.files.some((file) =>
      Boolean(getRootFolderFromRelativePath(file.webkitRelativePath)),
    );
  };

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

    let droppedFiles = Array.from(e.dataTransfer.files);
    let hasDirectories = false;

    try {
      const resolved = await getDroppedFilesFromDragEvent(e);
      droppedFiles = resolved.files;
      hasDirectories = resolved.hasDirectories;
    } catch {
      droppedFiles = Array.from(e.dataTransfer.files);
    }

    if (droppedFiles.length > 0) {
      try {
        const shouldTreatAsFolder = shouldTreatDropAsFolder({
          hasDirectories,
          files: droppedFiles,
        });

        if (shouldTreatAsFolder) {
          const hiddenFiltered =
            filterHiddenAndIgnoredFolderFiles(droppedFiles);
          const typeFiltered = filterFilesByTypes(
            hiddenFiltered.filtered,
            types,
          );
          const deduped = dedupeFolderRootIfNeeded({
            files: typeFiltered,
            existingRoots: new Set([
              ...Array.from(existingFolderRoots),
              ...Array.from(sessionUsedFolderRootsRef.current),
            ]),
            renameOnCollision: true,
          });

          const finalRootName = deduped.renamedRootName ?? deduped.rootName;
          if (finalRootName) {
            sessionUsedFolderRootsRef.current.add(finalRootName);
          }

          droppedFiles = deduped.files;
        }

        if (shouldTreatAsFolder && droppedFiles.length > 1000) {
          throw new Error(
            `Too many files detected (${droppedFiles.length}). This likely includes large/hidden directories. Please drop a smaller folder or exclude folders like node_modules.`,
          );
        }

        const filesIds = shouldTreatAsFolder
          ? await uploadFolder({ files: droppedFiles })
          : await uploadFiles({ files: droppedFiles });
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

  const handleSelectFolder = async () => {
    try {
      const selected = await createFileUpload({
        accept: types?.map((type) => `.${type}`).join(",") ?? "",
        multiple: true,
        webkitdirectory: true,
      });

      if (selected.length > 1000) {
        throw new Error(
          `Too many files detected (${selected.length}). This likely includes large/hidden directories. Please select a smaller folder or exclude folders like node_modules.`,
        );
      }

      const hiddenFiltered = filterHiddenAndIgnoredFolderFiles(selected);
      const typeFiltered = filterFilesByTypes(hiddenFiltered.filtered, types);
      const deduped = dedupeFolderRootIfNeeded({
        files: typeFiltered,
        existingRoots: new Set([
          ...Array.from(existingFolderRoots),
          ...Array.from(sessionUsedFolderRootsRef.current),
        ]),
        renameOnCollision: true,
      });

      const finalRootName = deduped.renamedRootName ?? deduped.rootName;
      if (finalRootName) {
        sessionUsedFolderRootsRef.current.add(finalRootName);
      }

      // When merging into an existing folder, we intentionally do not show a rename toast.

      const filesIds = await uploadFolder({ files: deduped.files });
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

  const handleSelectFiles = async () => {
    try {
      const filesIds = await uploadFiles({});
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
        onClick={handleSelectFiles}
        data-testid="drag-files-component"
        role="button"
        tabIndex={0}
      >
        <h3 className="text-sm font-semibold">
          {isDragging
            ? allowFolderSelection
              ? "Drop files or folders here"
              : "Drop files here"
            : allowFolderSelection
              ? "Click to select files (or drop a folder)"
              : "Click or drag files here"}
        </h3>
        {allowFolderSelection && (
          <div className="text-xs text-muted-foreground text-center max-w-md space-y-2">
            <p>Drag-and-drop supports both individual files and folders.</p>
            <p className="text-amber-600 dark:text-amber-400 font-medium">
              ⚠️ Avoid folders with large hidden directories (.mypy_cache, .git,
              node_modules, etc.)
            </p>
            <button
              type="button"
              className="text-xs underline underline-offset-4 text-foreground/80 hover:text-foreground"
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                handleSelectFolder();
              }}
            >
              Select a folder instead
            </button>
          </div>
        )}
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
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
          </span>
          <span className="font-semibold">
            {formatFileSize(maxFileSizeUpload)} max
          </span>
        </div>
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
