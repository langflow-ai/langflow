import { Input } from "@/components/ui/input";
import { IS_MAC } from "@/constants/constants";
import { usePostRenameFileV2 } from "@/controllers/API/queries/file-management/use-put-rename-file";
import { CustomLink } from "@/customization/components/custom-link";
import { sortByBoolean, sortByDate } from "@/pages/MainPage/utils/sort-flows";
import { FileType } from "@/types/file_management";
import Fuse from "fuse.js";
import { useCallback, useEffect, useMemo, useState } from "react";
import FilesRendererComponent from "../filesRendererComponent";

export default function RecentFilesComponent({
  files,
  selectedFiles,
  setSelectedFiles,
  types,
  isList,
}: {
  selectedFiles: string[];
  files: FileType[];
  setSelectedFiles: (files: string[]) => void;
  types: string[];
  isList: boolean;
}) {
  const filesWithDisabled = files.map((file) => {
    const fileExtension = file.path.split(".").pop()?.toLowerCase();
    return {
      ...file,
      type: fileExtension,
      disabled: !fileExtension || !types.includes(fileExtension),
    };
  });
  const [fuse, setFuse] = useState<Fuse<FileType>>(new Fuse([]));
  const [searchQuery, setSearchQuery] = useState("");
  const [lastSelectedIndex, setLastSelectedIndex] = useState<number | null>(
    null,
  );
  const [isShiftPressed, setIsShiftPressed] = useState(false);

  const { mutate: renameFile } = usePostRenameFileV2();

  const searchResults = useMemo(() => {
    const filteredFiles = searchQuery
      ? fuse.search(searchQuery).map(({ item }) => item)
      : (filesWithDisabled ?? []);
    return filteredFiles;
  }, [searchQuery, filesWithDisabled, selectedFiles, types]);

  const sortedSearchResults = useMemo(() => {
    return searchResults.toSorted((a, b) => {
      const selectedOrder = sortByBoolean(
        a.progress !== undefined,
        b.progress !== undefined,
      );
      return selectedOrder === 0
        ? sortByDate(a.updated_at ?? a.created_at, b.updated_at ?? b.created_at)
        : selectedOrder;
    });
  }, [searchResults]);

  useEffect(() => {
    if (filesWithDisabled) {
      setFuse(
        new Fuse(filesWithDisabled, {
          keys: ["name", "type"],
          threshold: 0.3,
        }),
      );
    }
  }, [filesWithDisabled]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Shift") {
        setIsShiftPressed(true);
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === "Shift") {
        setIsShiftPressed(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("keyup", handleKeyUp);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("keyup", handleKeyUp);
    };
  }, []);

  const handleFileSelect = useCallback(
    (filePath: string, index: number) => {
      setLastSelectedIndex(index);

      if (isShiftPressed && lastSelectedIndex !== null) {
        // Determine the range to select
        const start = Math.min(lastSelectedIndex, index);
        const end = Math.max(lastSelectedIndex, index);

        // Get all file paths in the range
        const filesToSelect = sortedSearchResults
          .slice(start, end + 1)
          .map((file) => file.path);

        // Check if all files in the range are already selected
        const allSelected = filesToSelect.every((path) =>
          selectedFiles.includes(path),
        );

        if (allSelected) {
          // If all are selected, unselect the range
          setSelectedFiles(
            selectedFiles.filter((path) => !filesToSelect.includes(path)),
          );
        } else {
          // Otherwise, add the range to selection
          const newSelection = [...selectedFiles];
          filesToSelect.forEach((path) => {
            if (!newSelection.includes(path)) {
              newSelection.push(path);
            }
          });
          setSelectedFiles(newSelection);
        }
      } else if (isList) {
        // In list mode, toggle the selection
        setSelectedFiles(
          selectedFiles.includes(filePath)
            ? selectedFiles.filter((path) => path !== filePath)
            : [...selectedFiles, filePath],
        );
      } else {
        // In non-list mode without shift, select only this file
        setSelectedFiles(
          selectedFiles.includes(filePath) && selectedFiles.length === 1
            ? []
            : [filePath],
        );
      }
    },
    [
      selectedFiles,
      lastSelectedIndex,
      sortedSearchResults,
      isShiftPressed,
      setSelectedFiles,
      isList,
    ],
  );

  const handleRename = (id: string, name: string) => {
    renameFile({ id, name });
  };

  return (
    <div className="flex flex-col gap-4 overflow-hidden">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <Input
            icon="Search"
            placeholder="Search files..."
            inputClassName="h-8"
            data-testid="search-files-input"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        {/* <div className="flex w-48 justify-end">
          <ImportButtonComponent variant="small" />
        </div> */}
      </div>
      <div
        className={`flex h-80 min-h-80 flex-col gap-1 overflow-y-auto overflow-x-hidden`}
      >
        {searchResults.length > 0 ? (
          <FilesRendererComponent
            files={sortedSearchResults}
            handleFileSelect={handleFileSelect}
            selectedFiles={selectedFiles}
            handleRename={handleRename}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-sm">
            <span>
              {searchQuery !== ""
                ? "No files found, try again "
                : "Upload or import files, "}
              or visit{" "}
              <CustomLink
                className="text-accent-pink-foreground underline"
                to="/files"
              >
                My Files.
              </CustomLink>
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
