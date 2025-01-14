import { usePostUploadFile } from "@/controllers/API/queries/files/use-post-upload-file";
import { createFileUpload } from "@/helpers/create-file-upload";
import useFileSizeValidator from "@/shared/hooks/use-file-size-validator";
import { cn } from "@/utils/utils";
import { useEffect, useRef } from "react";
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
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Clear component state
  useEffect(() => {
    if (disabled && value !== "") {
      handleOnNewValue({ value: "", file_path: "" }, { skipSnapshot: true });
    }
  }, [disabled, handleOnNewValue, value]);

  function checkFileType(fileName: string): boolean {
    if (!fileTypes?.length) return true;
    return fileTypes.some((type) =>
      fileName.toLowerCase().endsWith(type.toLowerCase()),
    );
  }

  const { mutate, isPending } = usePostUploadFile();

  const handleFileSelection = (file: File | null) => {
    if (!file) {
      setErrorData({
        title: "Error selecting file",
        list: ["No file was selected"],
      });
      return;
    }

    if (!validateFileSize(file)) {
      return;
    }

    if (!checkFileType(file.name)) {
      setErrorData({
        title: INVALID_FILE_ALERT,
        list: [fileTypes?.join(", ") || ""],
      });
      return;
    }

    mutate(
      { file, id: currentFlowId },
      {
        onSuccess: (data) => {
          const { file_path } = data;
          handleOnNewValue({ value: file.name, file_path });
        },
        onError: (error) => {
          console.error(CONSOLE_ERROR_MSG);
          setErrorData({
            title: "Error uploading file",
            list: [error.response?.data?.detail || "Unknown error occurred"],
          });
        },
      },
    );
  };

  const handleButtonClick = async (): Promise<void> => {
    try {
      const files = await createFileUpload({
        multiple: false,
        accept: fileTypes?.join(","),
      });

      if (files?.[0]) {
        handleFileSelection(files[0]);
      } else {
        fileInputRef.current?.click();
      }
    } catch (error) {
      console.error("Error in file upload:", error);
      fileInputRef.current?.click();
    }
  };

  const handleNativeInputChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0] || null;
    handleFileSelection(file);
    if (event.target) {
      event.target.value = "";
    }
  };

  const isDisabled = disabled || isPending;

  return (
    <div className="w-full">
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center gap-2.5">
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
              {/* Hidden native file input as fallback */}
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept={fileTypes?.join(",")}
                onChange={handleNativeInputChange}
                onClick={(e) => e.stopPropagation()}
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
        </div>
      </div>
    </div>
  );
}
