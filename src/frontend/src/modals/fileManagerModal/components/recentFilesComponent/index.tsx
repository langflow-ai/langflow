import { Input } from "@/components/ui/input";
import { usePostRenameFileV2 } from "@/controllers/API/queries/file-management/use-put-rename-file";
import { CustomLink } from "@/customization/components/custom-link";
import { sortByBoolean, sortByDate } from "@/pages/MainPage/utils/sort-flows";
import { FileType } from "@/types/file_management";
import Fuse from "fuse.js";
import { useEffect, useMemo, useState } from "react";
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
  const filesWithType = useMemo(
    () =>
      files.map((file) => ({
        ...file,
        type: file.path.split(".").pop()?.toLowerCase(),
      })),
    [files],
  );

  const fuse = useMemo(
    () =>
      new Fuse(filesWithType, {
        keys: ["name", "type"],
        threshold: 0.3,
      }),
    [filesWithType],
  );

  const [searchQuery, setSearchQuery] = useState("");

  const { mutate: renameFile } = usePostRenameFileV2();

  const searchResults = useMemo(() => {
    const filteredFiles = (
      searchQuery
        ? fuse.search(searchQuery).map(({ item }) => item)
        : (filesWithType ?? [])
    ).filter((file) => {
      const fileExtension = file.path.split(".").pop()?.toLowerCase();
      return fileExtension && (!types || types.includes(fileExtension));
    });
    return filteredFiles;
  }, [searchQuery, filesWithType, types]);

  const handleFileSelect = (filePath: string) => {
    setSelectedFiles(
      selectedFiles.includes(filePath)
        ? selectedFiles.filter((path) => path !== filePath)
        : isList
          ? [...selectedFiles, filePath]
          : [filePath],
    );
  };

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
            files={searchResults
              .toSorted((a, b) => {
                const selectedOrder = sortByBoolean(
                  a.progress !== undefined,
                  b.progress !== undefined,
                );
                return selectedOrder === 0
                  ? sortByDate(
                      a.updated_at ?? a.created_at,
                      b.updated_at ?? b.created_at,
                    )
                  : selectedOrder;
              })
              .slice(0, 10)}
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
