import { useEffect, useState } from "react";
import {
  CONSOLE_ERROR_MSG,
  INVALID_FILE_ALERT,
} from "../../constants/alerts_constants";
import { uploadFile } from "../../controllers/API";
import useAlertStore from "../../stores/alertStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { FileComponentType } from "../../types/components";
import IconComponent from "../genericIconComponent";

export default function InputFileComponent({
  value,
  onChange,
  disabled,
  fileTypes,
  onFileChange,
  editNode = false,
}: FileComponentType): JSX.Element {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const [myValue, setMyValue] = useState(value);
  const [loading, setLoading] = useState(false);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  // Clear component state
  useEffect(() => {
    if (disabled && value !== "") {
      setMyValue("");
      onChange("", true);
      onFileChange("");
    }
  }, [disabled, onChange]);

  function checkFileType(fileName: string): boolean {
    if (fileTypes === undefined) return true;
    for (let index = 0; index < fileTypes.length; index++) {
      if (fileName.endsWith(fileTypes[index])) {
        return true;
      }
    }
    return false;
  }

  useEffect(() => {
    setMyValue(value);
  }, [value]);

  const handleButtonClick = (): void => {
    // Create a file input element
    const input = document.createElement("input");
    document.body.appendChild(input);
    input.type = "file";
    input.accept = fileTypes?.join(",");
    input.style.display = "none"; // Hidden from view
    input.multiple = false; // Allow only one file selection
    const onChangeFile = (event: Event): void => {
      setLoading(true);

      // Get the selected file
      const file = (event.target as HTMLInputElement).files?.[0];

      // Check if the file type is correct
      if (file && checkFileType(file.name)) {
        // Upload the file
        uploadFile(file, currentFlowId)
          .then((res) => res.data)
          .then((data) => {
            // Get the file name from the response
            const { file_path } = data;

            // sets the value that goes to the backend
            onFileChange(file_path);
            // Update the state and callback with the name of the file
            // sets the value to the user
            setMyValue(file.name);
            onChange(file.name);
            setLoading(false);
          })
          .catch(() => {
            console.error(CONSOLE_ERROR_MSG);
            setLoading(false);
          });
      } else {
        // Show an error if the file type is not allowed
        setErrorData({
          title: INVALID_FILE_ALERT,
          list: fileTypes,
        });
        setLoading(false);
      }
    };

    input.addEventListener("change", onChangeFile);

    // Trigger the file selection dialog
    input.click();
  };

  return (
    <div className={disabled ? "input-component-div" : "w-full"}>
      <div className="input-file-component">
        <span
          onClick={handleButtonClick}
          className={
            editNode
              ? "input-edit-node input-dialog text-muted-foreground"
              : disabled
                ? "input-disable input-dialog primary-input"
                : "input-dialog primary-input text-muted-foreground"
          }
        >
          {myValue !== "" ? myValue : "No file"}
        </span>
        <button onClick={handleButtonClick}>
          {!editNode && !loading && (
            <IconComponent
              name="FileSearch2"
              className={
                "icons-parameters-comp" +
                (disabled ? " text-ring " : " hover:text-accent-foreground")
              }
            />
          )}
          {!editNode && loading && (
            <span className="loading loading-spinner loading-sm pointer-events-none h-8 pl-3"></span>
          )}
        </button>
      </div>
    </div>
  );
}
