import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { useGetFilesV2 } from "@/controllers/API/queries/file-management";
import { usePostUploadFile } from "@/controllers/API/queries/files/use-post-upload-file";
import { ENABLE_FILE_MANAGEMENT } from "@/customization/feature-flags";
import { createFileUpload } from "@/helpers/create-file-upload";
import FileManagerModal from "@/modals/fileManagerModal";
import FilesRendererComponent from "@/modals/fileManagerModal/components/filesRendererComponent";
import useFileSizeValidator from "@/shared/hooks/use-file-size-validator";
import { cn } from "@/utils/utils";
import useAlertStore from "../../../../../stores/alertStore";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../common/genericIconComponent";
import { Button } from "../../../../ui/button";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import type { FileComponentType, InputProps } from "../../types";

const sameList = (stored: unknown, next: string[]): boolean =>
  Array.isArray(stored) &&
  stored.length === next.length &&
  stored.every((entry, index) => entry === next[index]);

export default function InputFileComponent({
  value,
  file_path,
  handleOnNewValue,
  disabled,
  fileTypes,
  isList,
  tempFile = true,
  editNode = false,
  placeholder,
  allowFolderSelection = false,
  ariaLabelledBy,
}: InputProps<string, FileComponentType> & {
  allowFolderSelection?: boolean;
}): JSX.Element {
  const { t } = useTranslation();
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { validateFileSize } = useFileSizeValidator();

  // Clear component state
  useEffect(() => {
    if (disabled && value.length !== 0) {
      handleOnNewValue({ value: [], file_path: [] }, { skipSnapshot: true });
    }
  }, [disabled, handleOnNewValue]);

  function checkFileType(fileName: string): boolean {
    if (fileTypes === undefined) return true;

    // Extract the file extension
    const fileExtension = fileName.split(".").pop();

    // Check if the extracted extension is in the list of accepted file types
    return fileTypes.includes(fileExtension || "");
  }

  const { mutateAsync, isPending } = usePostUploadFile();

  const handleButtonClick = (): void => {
    createFileUpload({
      multiple: isList,
      accept: fileTypes?.join(","),
    }).then((files) => {
      if (files.length === 0) return;

      // Process files normally
      const filesToProcess: File[] = isList ? files : [files[0]];

      // Validate all files
      for (const file of filesToProcess) {
        try {
          validateFileSize(file);
        } catch (e) {
          if (e instanceof Error) {
            setErrorData({
              title: e.message,
            });
          }
          return;
        }
        if (!checkFileType(file.name)) {
          setErrorData({
            title: t("errors.invalidFile"),
            list: [fileTypes?.join(", ") || ""],
          });
          return;
        }
      }

      // Upload all files
      Promise.all(
        filesToProcess.map(
          (file) =>
            new Promise<{ file_name: string; file_path: string } | null>(
              async (resolve) => {
                try {
                  const data = await mutateAsync(
                    { file, id: currentFlowId },
                    {
                      onError: (error) => {
                        console.error(t("errors.uploadFile"));
                        setErrorData({
                          title: t("errors.upload"),
                          list: [error.response?.data?.detail],
                        });
                      },
                    },
                  );
                  resolve({
                    file_name: file.name,
                    file_path: data.file_path,
                  });
                } catch {
                  resolve(null);
                }
              },
            ),
        ),
      )
        .then((results) => {
          console.warn(results);
          // Filter out any failed uploads
          const successfulUploads = results.filter(
            (r): r is { file_name: string; file_path: string } => r !== null,
          );

          if (successfulUploads.length > 0) {
            const fileNames = successfulUploads.map(
              (result) => result.file_name,
            );
            const filePaths = successfulUploads.map(
              (result) => result.file_path,
            );

            // For single file mode, just use the first result
            // For list mode, join with commas
            handleOnNewValue({
              value: isList ? fileNames : fileNames[0],
              file_path: isList ? filePaths : filePaths[0],
            });
          }
        })
        .catch((e) => {
          console.error(e);
          // Error handling is done in the onError callback above
        });
    });
  };

  const handleDismissClick = () => {
    handleOnNewValue({
      value: "",
      file_path: "",
    });
  };

  const isDisabled = disabled || isPending;

  const {
    data: files,
    refetch: refetchFiles,
    isFetching: isFetchingFiles,
    dataUpdatedAt: filesUpdatedAt,
  } = useGetFilesV2({
    enabled: !!ENABLE_FILE_MANAGEMENT,
  });

  // Selected paths this component has already forced a fresh list read for.
  // A path is only dropped once a list fetched *after* we noticed it missing
  // still omits it.
  const recheckedPaths = useRef<Set<string>>(new Set());

  const [isFileManagerOpen, setIsFileManagerOpen] = useState(false);

  const selectedFiles = (
    isList
      ? Array.isArray(file_path)
        ? file_path.filter((value) => value !== "")
        : typeof file_path === "string"
          ? [file_path]
          : []
      : Array.isArray(file_path)
        ? (file_path ?? [])
        : [file_path ?? ""]
  ).filter((value) => value !== "");

  // Files the list can actually render a chip for. The list is a cache read,
  // not the record of what the user attached, so a selected path it does not
  // know about is left unrendered rather than treated as unselected.
  const renderedFiles = (files ?? []).filter((file) =>
    selectedFiles.includes(file.path),
  );

  // Names already stored on the node, indexed by their path, so a selected file
  // the current list omits keeps the name it was attached with.
  const storedNames = Array.isArray(value) ? value : [value ?? ""];
  const storedPaths = Array.isArray(file_path) ? file_path : [file_path ?? ""];

  const resolveName = (path: string): string =>
    (files ?? []).find((file) => file.path === path)?.name ??
    storedNames[storedPaths.indexOf(path)] ??
    "";

  // Reconcile the node with the file list: follow renames, and drop a file that
  // was really deleted. One response omitting the file is not evidence that it
  // is gone - the list can lag the upload that created it (the upload seeds the
  // cache optimistically, so the refetch it triggers is the first read that has
  // to find the file), or an older in-flight response can resolve last. Since
  // clearing value/file_path is persisted with the flow and is terminal - an
  // empty selection leaves nothing for a later, correct response to restore -
  // a missing path first forces a fresh read, and is only dropped when a list
  // fetched after that still omits it.
  //
  // The modal owns the selection while open; this effect's `file_path` snapshot
  // can lag one render behind it and would revert a just-uploaded file.
  useEffect(() => {
    if (files === undefined || tempFile || isFileManagerOpen) return;
    if (isFetchingFiles || selectedFiles.length === 0) return;

    const listedPaths = new Set(files.map((file) => file.path));
    for (const path of selectedFiles) {
      if (listedPaths.has(path)) recheckedPaths.current.delete(path);
    }

    const unverified = selectedFiles.filter(
      (path) => !listedPaths.has(path) && !recheckedPaths.current.has(path),
    );
    if (unverified.length > 0) {
      for (const path of unverified) recheckedPaths.current.add(path);
      refetchFiles();
      return;
    }

    const nextPaths = selectedFiles.filter((path) => listedPaths.has(path));
    const nextNames = nextPaths.map(resolveName);

    if (isList) {
      if (sameList(value, nextNames) && sameList(file_path, nextPaths)) return;
      handleOnNewValue({ value: nextNames, file_path: nextPaths });
      return;
    }

    const nextName = nextNames[0] ?? "";
    const nextPath = nextPaths[0] ?? "";
    if (value === nextName && file_path === nextPath) return;
    handleOnNewValue({ value: nextName, file_path: nextPath });
  }, [
    files,
    filesUpdatedAt,
    isFetchingFiles,
    value,
    file_path,
    isFileManagerOpen,
  ]);

  return (
    <div className="w-full">
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center gap-2.5">
          {ENABLE_FILE_MANAGEMENT && !tempFile ? (
            files && (
              <div className="relative flex w-full flex-col gap-2">
                <div className="nopan nowheel flex max-h-44 flex-col overflow-y-auto">
                  <FilesRendererComponent
                    files={renderedFiles}
                    handleRemove={(path) => {
                      const newSelectedFiles = selectedFiles.filter(
                        (file) => file !== path,
                      );
                      handleOnNewValue({
                        value: isList
                          ? newSelectedFiles.map(resolveName)
                          : resolveName(newSelectedFiles[0] ?? ""),
                        file_path: isList
                          ? newSelectedFiles
                          : (newSelectedFiles[0] ?? ""),
                      });
                    }}
                  />
                </div>
                <FileManagerModal
                  files={files}
                  onOpenChange={setIsFileManagerOpen}
                  selectedFiles={selectedFiles}
                  handleSubmit={(submittedFiles) => {
                    handleOnNewValue({
                      value: isList
                        ? submittedFiles.map(resolveName)
                        : resolveName(submittedFiles[0] ?? ""),
                      file_path: isList
                        ? submittedFiles
                        : (submittedFiles[0] ?? ""),
                    });
                  }}
                  disabled={isDisabled}
                  types={fileTypes}
                  isList={isList}
                  allowFolderSelection={allowFolderSelection}
                >
                  {(renderedFiles.length === 0 || isList) && (
                    <div data-testid="input-file-component" className="w-full">
                      <Button
                        disabled={isDisabled}
                        variant={
                          renderedFiles.length !== 0 ? "ghost" : "default"
                        }
                        size={renderedFiles.length !== 0 ? "iconMd" : "default"}
                        className={cn(
                          renderedFiles.length !== 0
                            ? "hit-area-icon absolute -top-8 right-0"
                            : "w-full",
                          "font-semibold",
                        )}
                        data-testid="button_open_file_management"
                        aria-label={
                          isList
                            ? t("fileManager.selectFiles")
                            : t("fileManager.selectFile")
                        }
                      >
                        {disabled ? (
                          getPlaceholder(disabled, placeholder)
                        ) : renderedFiles.length !== 0 ? (
                          <ForwardedIconComponent
                            name="Plus"
                            className="icon-size"
                            strokeWidth={ICON_STROKE_WIDTH}
                          />
                        ) : (
                          <div>
                            {isList
                              ? t("fileManager.selectFiles")
                              : t("fileManager.selectFile")}
                          </div>
                        )}
                      </Button>
                    </div>
                  )}
                </FileManagerModal>
              </div>
            )
          ) : (
            <div className="relative flex w-full">
              <div className="w-full">
                <input
                  data-testid="input-file-component"
                  type="text"
                  className={cn(
                    "primary-input h-9 w-full cursor-pointer rounded-r-none text-sm focus:outline-none focus:ring-0",
                    !value && "text-placeholder-foreground",
                    editNode && "h-6",
                  )}
                  value={value || "Upload a file..."}
                  readOnly
                  disabled={isDisabled}
                  onClick={handleButtonClick}
                  aria-labelledby={ariaLabelledBy}
                  aria-label={
                    ariaLabelledBy ? undefined : t("fileManager.selectFile")
                  }
                />
              </div>
              <div>
                <Button
                  className={cn(
                    "h-9 w-9 rounded-l-none group relative",
                    value &&
                      "bg-accent-emerald-foreground hover:bg-accent-red-foreground ring-accent-emerald-foreground hover:ring-accent-red-foreground",
                    isDisabled &&
                      "relative top-[1px] h-9 ring-1 ring-border ring-offset-0 hover:ring-border",
                    editNode && "h-6",
                  )}
                  onClick={value ? handleDismissClick : handleButtonClick}
                  disabled={isDisabled}
                  size="icon"
                  data-testid="button_upload_file"
                  aria-label={value ? t("files.remove") : t("files.uploadFile")}
                >
                  <IconComponent
                    name={value ? "CircleCheckBig" : "Upload"}
                    className={cn(
                      value && "text-background group-hover:opacity-0",
                      isDisabled && "text-muted-foreground",
                      "h-4 w-4 absolute transition-opacity duration-200",
                    )}
                    strokeWidth={2}
                  />
                  <IconComponent
                    name={"X"}
                    className={cn(
                      "h-4 w-4 text-background opacity-0 absolute transition-opacity duration-200",
                      value && "group-hover:opacity-100",
                    )}
                    strokeWidth={2}
                  />
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
