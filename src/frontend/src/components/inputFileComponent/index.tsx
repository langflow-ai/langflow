import { useContext, useEffect, useState } from "react";
import { alertContext } from "../../contexts/alertContext";
import { FileComponentType } from "../../types/components";
import { TabsContext } from "../../contexts/tabsContext";
import { INPUT_STYLE } from "../../constants";
import { FileSearch2 } from "lucide-react";
import { uploadFile } from "../../controllers/API";

export default function InputFileComponent({
  value,
  onChange,
  disabled,
  suffixes,
  fileTypes,
  onFileChange,
  editNode = false,
}: FileComponentType) {
  const [myValue, setMyValue] = useState(value);
  const [loading, setLoading] = useState(false);
  const { setErrorData } = useContext(alertContext);
  const { tabId } = useContext(TabsContext);
  useEffect(() => {
    if (disabled) {
      setMyValue("");
      onChange("");
      onFileChange("");
    }
  }, [disabled, onChange]);

  function checkFileType(fileName: string): boolean {
    for (let index = 0; index < suffixes.length; index++) {
      if (fileName.endsWith(suffixes[index])) {
        return true;
      }
    }
    return false;
  }

  useEffect(() => {
    setMyValue(value);
  }, [value]);

  const handleButtonClick = () => {
    // Create a file input element
    const input = document.createElement("input");
    input.type = "file";
    input.accept = suffixes.join(",");
    input.style.display = "none"; // Hidden from view
    input.multiple = false; // Allow only one file selection

    input.onchange = (e: Event) => {
      setLoading(true);

      // Get the selected file
      const file = (e.target as HTMLInputElement).files?.[0];

      // Check if the file type is correct
      if (file && checkFileType(file.name)) {
        // Upload the file
        uploadFile(file, tabId)
          .then((res) => res.data)
          .then((data) => {
            console.log("File uploaded successfully");
            // Get the file name from the response
            const { file_path } = data;
            console.log("File name:", file_path);

            // Update the state and callback with the name of the file
            // sets the value to the user
            setMyValue(file.name);
            onChange(file.name);
            // sets the value that goes to the backend
            onFileChange(file_path);
            setLoading(false);
          })
          .catch(() => {
            console.error("Error occurred while uploading file");
            setLoading(false);
          });
      } else {
        // Show an error if the file type is not allowed
        setErrorData({
          title:
            "Please select a valid file. Only these file types are allowed:",
          list: fileTypes,
        });
        setLoading(false);
      }
    };

    // Trigger the file selection dialog
    input.click();
  };

  return (
    <div
      className={
        disabled ? "pointer-events-none cursor-not-allowed w-full" : "w-full"
      }
    >
      <div className="w-full flex items-center gap-2">
        <span
          onClick={handleButtonClick}
          className={
            editNode
              ? "truncate placeholder:text-center text-gray-500 block w-full pt-0.5 pb-0.5 form-input dark:bg-gray-900 dark:text-gray-300 dark:border-gray-600 rounded-md border-gray-300 shadow-sm sm:text-sm border-1" +
                INPUT_STYLE
              : "truncate block w-full text-gray-500 dark:text-gray-300 px-3 py-2 rounded-md border border-gray-300 dark:border-gray-700 shadow-sm sm:text-sm" +
                INPUT_STYLE +
                (disabled ? " bg-gray-200" : "")
          }
        >
          {myValue !== "" ? myValue : "No file"}
        </span>
        <button onClick={handleButtonClick}>
          {!editNode && !loading && (
            <FileSearch2 className="w-6 h-6 hover:text-ring" />
          )}
          {!editNode && loading && (
            <span className="loading loading-spinner loading-sm pl-3 h-8 pointer-events-none"></span>
          )}
        </button>
      </div>
    </div>
  );
}
