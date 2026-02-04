import Fuse from "fuse.js";
import { useCallback, useEffect, useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { useDeleteFilesV2 } from "@/controllers/API/queries/file-management/use-delete-files";
import { usePostRenameFileV2 } from "@/controllers/API/queries/file-management/use-put-rename-file";
import { CustomLink } from "@/customization/components/custom-link";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import { sortByBoolean, sortByDate } from "@/pages/MainPage/utils/sort-flows";
import useAlertStore from "@/stores/alertStore";
import type { FileType } from "@/types/file_management";
import { cn } from "@/utils/utils";
import FilesRendererComponent from "../filesRendererComponent";
import FileRendererComponent from "../filesRendererComponent/components/fileRendererComponent";
import {
  buildFileTree,
  collectFolderKeys,
  collectLeafPaths,
  type FileTreeNode,
  getFileHierarchyPath,
} from "./recent-files-helpers";

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
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const filesWithDisabled = useMemo(() => {
    return files.map((file) => {
      const fileExtension = file.path.split(".").pop()?.toLowerCase();
      return {
        ...file,
        type: fileExtension,
        disabled: !fileExtension || !types.includes(fileExtension),
        relativePath: getFileHierarchyPath(file),
      };
    });
  }, [files, types]);

  const selectedFileIds = useMemo(() => {
    const ids = filesWithDisabled
      .filter((file) => selectedFiles.includes(file.path))
      .map((file) => file.id)
      .filter(Boolean);
    return Array.from(new Set(ids));
  }, [filesWithDisabled, selectedFiles]);

  const { mutate: deleteFiles, isPending: isDeleting } = useDeleteFilesV2();
  const fuse = useMemo(
    () =>
      new Fuse(filesWithDisabled, {
        keys: ["name", "type", "relativePath"],
        threshold: 0.3,
      }),
    [filesWithDisabled],
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [lastClickedIndex, setLastClickedIndex] = useState<number | null>(null);
  const [isShiftPressed, setIsShiftPressed] = useState(false);
  const [expandedFolders, setExpandedFolders] = useState<
    Record<string, boolean>
  >({});

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

  const { tree, leafFilesInOrder, hasHierarchy } = useMemo(
    () => buildFileTree(sortedSearchResults),
    [sortedSearchResults],
  );

  const leafIndexByPath = useMemo(() => {
    return new Map(leafFilesInOrder.map((file, index) => [file.path, index]));
  }, [leafFilesInOrder]);

  const isHierarchyView = useMemo(() => {
    return searchQuery === "" && hasHierarchy;
  }, [searchQuery, hasHierarchy]);

  useEffect(() => {
    if (!isHierarchyView) return;

    const folderKeys = collectFolderKeys(tree);

    setExpandedFolders((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const key of folderKeys) {
        if (next[key] === undefined) {
          next[key] = true;
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [isHierarchyView, tree]);

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

      const activeList = isHierarchyView
        ? leafFilesInOrder
        : sortedSearchResults;

      if (isShiftPressed && lastClickedIndex !== null) {
        // Select range - keep existing selection and add the range
        const start = Math.min(lastClickedIndex, index);
        const end = Math.max(lastClickedIndex, index);

        // Get all file paths in the range
        const rangeFilePaths = activeList
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
      leafFilesInOrder,
      isHierarchyView,
      isShiftPressed,
      setSelectedFiles,
    ],
  );

  const handleRename = (id: string, name: string) => {
    renameFile({ id, name });
  };

  const handleBulkDelete = () => {
    if (selectedFileIds.length === 0) return;
    deleteFiles(
      {
        ids: selectedFileIds,
      },
      {
        onSuccess: (data) => {
          setSuccessData({
            title: data?.message ?? "Files deleted successfully",
          });
          setSelectedFiles([]);
        },
        onError: (error: any) => {
          setErrorData({
            title: "Error deleting files",
            list: [
              error?.message || "An error occurred while deleting the files",
            ],
          });
        },
      },
    );
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
        {selectedFiles.length > 0 && (
          <div className="ml-2 flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {selectedFiles.length} selected
            </span>
            <DeleteConfirmationModal
              onConfirm={() => handleBulkDelete()}
              description={`file${selectedFiles.length > 1 ? "s" : ""}`}
            >
              <Button
                variant="destructive"
                size="iconMd"
                className="px-2.5 !text-mmd"
                loading={isDeleting}
                data-testid="bulk-delete-files-modal-btn"
              >
                <ForwardedIconComponent name="Trash2" />
                Delete
              </Button>
            </DeleteConfirmationModal>
          </div>
        )}
        {/* <div className="flex w-48 justify-end">
          <ImportButtonComponent variant="small" />
        </div> */}
      </div>
      <div
        className={`flex h-80 min-h-80 flex-col gap-1 overflow-y-auto overflow-x-hidden`}
      >
        {searchResults.length > 0 ? (
          isHierarchyView ? (
            <div className="flex flex-col gap-1">
              {(() => {
                const renderNodes = (nodes: FileTreeNode[], depth = 0) => {
                  return nodes.map((node) => {
                    if (node.kind === "folder") {
                      const isExpanded = expandedFolders[node.pathKey] ?? true;
                      const leafPaths = collectLeafPaths(node);
                      const selectedCount = leafPaths.filter((p) =>
                        selectedFiles.includes(p),
                      ).length;
                      const isChecked =
                        leafPaths.length > 0 &&
                        selectedCount === leafPaths.length;
                      const isIndeterminate =
                        selectedCount > 0 && selectedCount < leafPaths.length;

                      return (
                        <div key={node.pathKey}>
                          <div
                            className={cn(
                              "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-foreground/90",
                              "cursor-pointer select-none hover:bg-accent",
                            )}
                            style={{ paddingLeft: 12 + depth * 12 }}
                            role="button"
                            tabIndex={0}
                            aria-expanded={isExpanded}
                            onClick={(e) => {
                              e.preventDefault();
                              setExpandedFolders((prev) => {
                                const current = prev[node.pathKey] ?? true;
                                return { ...prev, [node.pathKey]: !current };
                              });
                            }}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" || e.key === " ") {
                                e.preventDefault();
                                setExpandedFolders((prev) => {
                                  const current = prev[node.pathKey] ?? true;
                                  return { ...prev, [node.pathKey]: !current };
                                });
                              }
                            }}
                          >
                            <div onClick={(e) => e.stopPropagation()}>
                              <Checkbox
                                checked={
                                  isIndeterminate ? "indeterminate" : isChecked
                                }
                                disabled={leafPaths.length === 0}
                                onCheckedChange={() => {
                                  if (leafPaths.length === 0) return;

                                  // If any are unselected -> select all, else deselect all.
                                  const shouldSelect =
                                    selectedCount !== leafPaths.length;

                                  if (!isList) {
                                    setSelectedFiles(
                                      shouldSelect ? [leafPaths[0]] : [],
                                    );
                                    return;
                                  }

                                  if (shouldSelect) {
                                    setSelectedFiles(
                                      Array.from(
                                        new Set([
                                          ...selectedFiles,
                                          ...leafPaths,
                                        ]),
                                      ),
                                    );
                                  } else {
                                    const toRemove = new Set(leafPaths);
                                    setSelectedFiles(
                                      selectedFiles.filter(
                                        (p) => !toRemove.has(p),
                                      ),
                                    );
                                  }
                                }}
                                className="focus-visible:ring-0"
                              />
                            </div>
                            <ForwardedIconComponent
                              name="Folder"
                              className="h-4 w-4 text-muted-foreground"
                            />
                            <span className="truncate">{node.name}</span>
                            <ForwardedIconComponent
                              name="ChevronRight"
                              className={cn(
                                "ml-auto h-4 w-4 text-muted-foreground transition-transform",
                                isExpanded ? "rotate-90" : "rotate-0",
                              )}
                            />
                          </div>
                          {isExpanded ? (
                            <div>{renderNodes(node.children, depth + 1)}</div>
                          ) : null}
                        </div>
                      );
                    }

                    const leafIndex = leafIndexByPath.get(node.file.path) ?? 0;

                    return (
                      <div
                        key={`${node.pathKey}:${node.file.path}`}
                        style={{ paddingLeft: depth * 12 }}
                      >
                        <FileRendererComponent
                          file={node.file}
                          handleFileSelect={(path) =>
                            handleFileSelect(path, leafIndex)
                          }
                          selectedFiles={selectedFiles}
                          handleRename={handleRename}
                          isShiftPressed={isShiftPressed}
                          index={leafIndex}
                        />
                      </div>
                    );
                  });
                };

                return renderNodes(tree);
              })()}
            </div>
          ) : (
            <FilesRendererComponent
              files={sortedSearchResults}
              handleFileSelect={handleFileSelect}
              selectedFiles={selectedFiles}
              handleRename={handleRename}
              isShiftPressed={isShiftPressed}
            />
          )
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
