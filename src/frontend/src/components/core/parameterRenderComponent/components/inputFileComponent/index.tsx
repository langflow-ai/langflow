import { usePostUploadFile } from "@/controllers/API/queries/files/use-post-upload-file";
import { ENABLE_FILE_MANAGEMENT } from "@/customization/feature-flags";
import { createFileUpload } from "@/helpers/create-file-upload";
import FileManagerModal from "@/modals/fileManagerModal";
import FilesRendererComponent from "@/modals/fileManagerModal/components/filesRendererComponent";
import useFileSizeValidator from "@/shared/hooks/use-file-size-validator";
import { cn } from "@/utils/utils";
import { useEffect, useState } from "react";
import {
  CONSOLE_ERROR_MSG,
  INVALID_FILE_ALERT,
} from "../../../../../constants/alerts_constants";
import useAlertStore from "../../../../../stores/alertStore";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import IconComponent from "../../../../common/genericIconComponent";
import { Button } from "../../../../ui/button";
import { FileComponentType, InputProps } from "../../types";

export default function InputFileComponent({
  value,
  handleOnNewValue,
  disabled,
  fileTypes,
  editNode = false,
  id,
}: InputProps<string, FileComponentType>): JSX.Element {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { validateFileSize } = useFileSizeValidator(setErrorData);

  // Clear component state
  useEffect(() => {
    if (disabled && value !== "") {
      handleOnNewValue({ value: "", file_path: "" }, { skipSnapshot: true });
    }
  }, [disabled, handleOnNewValue]);

  function checkFileType(fileName: string): boolean {
    if (fileTypes === undefined) return true;
    for (let index = 0; index < fileTypes.length; index++) {
      if (fileName.endsWith(fileTypes[index])) {
        return true;
      }
    }
    return false;
  }

  const { mutate, isPending } = usePostUploadFile();

  const handleButtonClick = (): void => {
    createFileUpload({ multiple: false, accept: fileTypes?.join(",") }).then(
      (files) => {
        const file = files[0];
        if (file) {
          if (!validateFileSize(file)) {
            return;
          }

          if (checkFileType(file.name)) {
            // Upload the file
            mutate(
              { file, id: currentFlowId },
              {
                onSuccess: (data) => {
                  // Get the file name from the response
                  const { file_path } = data;

                  // sets the value that goes to the backend
                  // Update the state and on with the name of the file
                  // sets the value to the user
                  handleOnNewValue({ value: file.name, file_path });
                },
                onError: (error) => {
                  console.error(CONSOLE_ERROR_MSG);
                  setErrorData({
                    title: "Error uploading file",
                    list: [error.response?.data?.detail],
                  });
                },
              },
            );
          } else {
            // Show an error if the file type is not allowed
            setErrorData({
              title: INVALID_FILE_ALERT,
              list: [fileTypes?.join(", ") || ""],
            });
          }
        }
      },
    );
  };

  const isDisabled = disabled || isPending;

  const files = [
    {
      type: "json",
      name: "user_profile_data.json",
      size: "640 KB",
    },
    {
      type: "csv",
      name: "Q4_Reports.csv",
      size: "80 KB",
    },
    {
      type: "txt",
      name: "Highschool Speech.txt",
      size: "10 KB",
    },
    {
      type: "pdf",
      name: "logoconcepts.pdf",
      size: "1.2 MB",
    },
  ];

  const [selectedFiles, setSelectedFiles] = useState<string[]>(
    files.map((file) => file.name),
  );

  return (
    <div className="w-full">
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center gap-2.5">
          {ENABLE_FILE_MANAGEMENT ? (
            <div className="flex w-full flex-col gap-2">
              <div className="flex flex-col">
                <FilesRendererComponent
                  files={files.filter((file) =>
                    selectedFiles.includes(file.name),
                  )}
                  handleDelete={(fileName) => {
                    setSelectedFiles(
                      selectedFiles.filter((file) => file !== fileName),
                    );
                  }}
                />
              </div>
              <FileManagerModal
                selectedFiles={selectedFiles}
                handleSubmit={(selectedFiles) => {
                  setSelectedFiles(selectedFiles);
                }}
                disabled={isDisabled}
              >
                <Button
                  disabled={isDisabled}
                  className="font-semibold"
                  data-testid="button_open_file_management"
                >
                  <div>Select files</div>
                </Button>
              </FileManagerModal>
            </div>
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
