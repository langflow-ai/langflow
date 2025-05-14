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
  const filesWithDisabled = useMemo(
    () =>
      files.map((file) => {
        const fileExtension = file.path.split(".").pop()?.toLowerCase();
        return {
          ...file,
          type: fileExtension,
          disabled: !fileExtension || !types.includes(fileExtension),
        };
      }),
    [files, types],
  );
  const fuse = useMemo(
    () =>
      new Fuse(filesWithDisabled, {
        keys: ["name", "type"],
        threshold: 0.3,
      }),
    [filesWithDisabled],
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [lastClickedIndex, setLastClickedIndex] = useState<number | null>(null);
  const [isShiftPressed, setIsShiftPressed] = useState(false);

  const { mutate: renameFile } = usePostRenameFileV2();

  const searchResults = useMemo(() => {
    const filteredFiles = searchQuery
      ? fuse.search(searchQuery).map(({ item }) => item)
      : (filesWithDisabled ?? []);
    return filteredFiles;
  }, [searchQuery, filesWithDisabled, types]);

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

    // Reset key states when window loses focus
    const handleBlur = () => {
      setIsShiftPressed(false);
    };

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("keyup", handleKeyUp);
    window.addEventListener("blur", handleBlur);

    // Clean up event listeners when component unmounts
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("keyup", handleKeyUp);
      window.removeEventListener("blur", handleBlur);

      // Reset key state on unmount
      setIsShiftPressed(false);
    };
  }, []);

  const handleFileSelect = useCallback(
    (filePath: string, index: number) => {
      // Standard file selection behavior:
      // 1. Click: Select only this file
      // 2. Ctrl/Cmd + Click: Toggle selection for this file, keeping other selections
      // 3. Shift + Click: Select range from last clicked to current file

      if (isShiftPressed && lastClickedIndex !== null) {
        // Select range - keep existing selection and add the range
        const start = Math.min(lastClickedIndex, index);
        const end = Math.max(lastClickedIndex, index);

        // Get all file paths in the range
        const rangeFilePaths = sortedSearchResults
          .slice(start, end + 1)
          .filter((file) => !file.disabled)
          .map((file) => file.path);

        return setSelectedFiles(rangeFilePaths);
      } else {
        // Ctrl/Cmd + Click: Toggle selection for this item while keeping others
        setLastClickedIndex(index);

        if (selectedFiles.includes(filePath)) {
          setSelectedFiles(selectedFiles.filter((path) => path !== filePath));
        } else {
          setSelectedFiles([...selectedFiles, filePath]);
        }
      }
    },
    [
      selectedFiles,
      lastClickedIndex,
      sortedSearchResults,
      isShiftPressed,
      setSelectedFiles,
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
            isShiftPressed={isShiftPressed}
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
