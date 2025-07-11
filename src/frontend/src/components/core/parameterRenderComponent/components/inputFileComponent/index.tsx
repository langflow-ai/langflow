import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { useGetFilesV2 } from "@/controllers/API/queries/file-management";
import { usePostUploadFile } from "@/controllers/API/queries/files/use-post-upload-file";
import { ENABLE_FILE_MANAGEMENT } from "@/customization/feature-flags";
import { createFileUpload } from "@/helpers/create-file-upload";
import FileManagerModal from "@/modals/fileManagerModal";
import FilesRendererComponent from "@/modals/fileManagerModal/components/filesRendererComponent";
import useFileSizeValidator from "@/shared/hooks/use-file-size-validator";
import { cn } from "@/utils/utils";
import { useEffect } from "react";
import {
  CONSOLE_ERROR_MSG,
  INVALID_FILE_ALERT,
} from "../../../../../constants/alerts_constants";
import useAlertStore from "../../../../../stores/alertStore";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../common/genericIconComponent";
import { Button } from "../../../../ui/button";
import type { FileComponentType, InputProps } from "../../types";

export default function InputFileComponent({
  value,
  file_path,
  handleOnNewValue,
  disabled,
  fileTypes,
  isList,
  tempFile = true,
  editNode = false,
  id,
}: InputProps<string, FileComponentType>): JSX.Element {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { validateFileSize } = useFileSizeValidator();

  // Clear component state
  useEffect(() => {
    if (disabled && value !== "") {
      handleOnNewValue({ value: "", file_path: "" }, { skipSnapshot: true });
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
    createFileUpload({ multiple: isList, accept: fileTypes?.join(",") }).then(
      (files) => {
        if (files.length === 0) return;

        // For single file mode, only process the first file
        const filesToProcess = isList ? files : [files[0]];

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
              title: INVALID_FILE_ALERT,
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
                  const data = await mutateAsync(
                    { file, id: currentFlowId },
                    {
                      onError: (error) => {
                        console.error(CONSOLE_ERROR_MSG);
                        setErrorData({
                          title: "Error uploading file",
                          list: [error.response?.data?.detail],
                        });
                        resolve(null);
                      },
                    },
                  );
                  resolve({
                    file_name: file.name,
                    file_path: data.file_path,
                  });
                },
              ),
          ),
        )
          .then((results) => {
            console.log(results);
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
            console.log(e);
            // Error handling is done in the onError callback above
          });
      },
    );
  };

  const isDisabled = disabled || isPending;

  const { data: files } = useGetFilesV2({
    enabled: !!ENABLE_FILE_MANAGEMENT,
  });

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

  useEffect(() => {
    if (files !== undefined && !tempFile) {
      if (isList) {
        if (
          Array.isArray(value) &&
          value.every((v) => files?.find((f) => f.name === v)) &&
          Array.isArray(file_path) &&
          file_path.every((v) => files?.find((f) => f.path === v))
        ) {
          return;
        }
      } else {
        if (
          typeof value === "string" &&
          files?.find((f) => f.name === value) &&
          typeof file_path === "string" &&
          files?.find((f) => f.path === file_path)
        ) {
          return;
        }
      }
      handleOnNewValue({
        value: isList
          ? (files
              ?.filter((f) => selectedFiles.includes(f.path))
              .map((f) => f.name) ?? [])
          : (files?.find((f) => selectedFiles.includes(f.path))?.name ?? ""),
        file_path: isList
          ? (files
              ?.filter((f) => selectedFiles.includes(f.path))
              .map((f) => f.path) ?? [])
          : (files?.find((f) => selectedFiles.includes(f.path))?.path ?? ""),
      });
    }
  }, [files, value, file_path]);

  return (
    <div className="w-full">
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center gap-2.5">
          {ENABLE_FILE_MANAGEMENT && !tempFile ? (
            files && (
              <div className="relative flex w-full flex-col gap-2">
                <div className="nopan nowheel flex max-h-44 flex-col overflow-y-auto">
                  <FilesRendererComponent
                    files={files.filter((file) =>
                      selectedFiles.includes(file.path),
                    )}
                    handleRemove={(path) => {
                      const newSelectedFiles = selectedFiles.filter(
                        (file) => file !== path,
                      );
                      handleOnNewValue({
                        value: isList
                          ? newSelectedFiles.map(
                              (file) =>
                                files.find((f) => f.path === file)?.name,
                            )
                          : (files.find((f) => f.path == newSelectedFiles[0]) ??
                            ""),
                        file_path: isList
                          ? newSelectedFiles
                          : (newSelectedFiles[0] ?? ""),
                      });
                    }}
                  />
                </div>
                <FileManagerModal
                  files={files}
                  selectedFiles={selectedFiles}
                  handleSubmit={(selectedFiles) => {
                    handleOnNewValue({
                      value: isList
                        ? selectedFiles.map(
                            (file) => files.find((f) => f.path === file)?.name,
                          )
                        : (files.find((f) => f.path == selectedFiles[0]) ?? ""),
                      file_path: isList
                        ? selectedFiles
                        : (selectedFiles[0] ?? ""),
                    });
                  }}
                  disabled={isDisabled}
                  types={fileTypes}
                  isList={isList}
                >
                  {(selectedFiles.length === 0 || isList) && (
                    <div data-testid="input-file-component" className="w-full">
                      <Button
                        disabled={isDisabled}
                        variant={
                          selectedFiles.length !== 0 ? "ghost" : "default"
                        }
                        size={selectedFiles.length !== 0 ? "iconMd" : "default"}
                        className={cn(
                          selectedFiles.length !== 0
                            ? "hit-area-icon absolute -top-8 right-0"
                            : "w-full",
                          "font-semibold",
                        )}
                        data-testid="button_open_file_management"
                      >
                        {selectedFiles.length !== 0 ? (
                          <ForwardedIconComponent
                            name="Plus"
                            className="icon-size"
                            strokeWidth={ICON_STROKE_WIDTH}
                          />
                        ) : (
                          <div>Select file{isList ? "s" : ""}</div>
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
                    "primary-input h-9 w-full cursor-pointer rounded-r-none text-sm focus:border-border focus:outline-none focus:ring-0",
                    !value && "text-placeholder-foreground",
                    editNode && "h-6",
                  )}
                  value={value || "Upload a file..."}
                  readOnly
                  disabled={isDisabled}
                  onClick={handleButtonClick}
                />
              </div>
              <div>
                <Button
                  className={cn(
                    "h-9 w-9 rounded-l-none",
                    value &&
                      "bg-accent-emerald-foreground ring-accent-emerald-foreground hover:bg-accent-emerald-foreground",
                    isDisabled &&
                      "relative top-[1px] h-9 ring-1 ring-border ring-offset-0 hover:ring-border",
                    editNode && "h-6",
                  )}
                  onClick={handleButtonClick}
                  disabled={isDisabled}
                  size="icon"
                  data-testid="button_upload_file"
                >
                  <IconComponent
                    name={value ? "CircleCheckBig" : "Upload"}
                    className={cn(
                      value && "text-background",
                      isDisabled && "text-muted-foreground",
                      "h-4 w-4",
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
