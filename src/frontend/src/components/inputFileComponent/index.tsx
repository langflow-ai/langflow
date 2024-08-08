import { usePostUploadFile } from "@/controllers/API/queries/files/use-post-upload-file";
import { createFileUpload } from "@/helpers/create-file-upload";
import { useEffect } from "react";
import {
  CONSOLE_ERROR_MSG,
  INVALID_FILE_ALERT,
} from "../../constants/alerts_constants";
import useAlertStore from "../../stores/alertStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { FileComponentType } from "../../types/components";
import IconComponent from "../genericIconComponent";
import { Button } from "../ui/button";

export default function InputFileComponent({
  value,
  handleOnNewValue,
  disabled,
  fileTypes,
  editNode = false,
  id,
}: FileComponentType): JSX.Element {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const setErrorData = useAlertStore((state) => state.setErrorData);

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
                onError: () => {
                  console.error(CONSOLE_ERROR_MSG);
                },
              },
            );
          } else {
            // Show an error if the file type is not allowed
            setErrorData({
              title: INVALID_FILE_ALERT,
              list: fileTypes,
            });
          }
        }
      },
    );
  };

  return (
    <div className={disabled ? "input-component-div" : "w-full"}>
      <div className="input-file-component gap-3">
        <span
          data-testid={id}
          onClick={handleButtonClick}
          className={
            editNode
              ? "input-edit-node input-dialog text-muted-foreground"
              : disabled
                ? "input-disable input-dialog primary-input"
                : "input-dialog primary-input text-muted-foreground"
          }
        >
          {value !== "" ? value : "No file"}
        </span>
        {!editNode && (
          <Button
            unstyled
            className="inline-flex items-center justify-center"
            onClick={handleButtonClick}
            loading={isPending}
            disabled={disabled}
          >
            <IconComponent
              name="FileSearch2"
              className="icons-parameters-comp shrink-0"
            />
          </Button>
        )}
      </div>
    </div>
  );
}
