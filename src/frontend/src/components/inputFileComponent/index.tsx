import { DocumentMagnifyingGlassIcon } from "@heroicons/react/24/outline";
import { useContext, useEffect, useState } from "react";
import { alertContext } from "../../contexts/alertContext";
import { FileComponentType } from "../../types/components";
import { TabsContext } from "../../contexts/tabsContext";

export default function InputFileComponent({
  value,
  onChange,
  disabled,
  suffixes,
  fileTypes,
  onFileChange,
}: FileComponentType) {
  const [myValue, setMyValue] = useState(value);
  const { setErrorData } = useContext(alertContext);
  const { flows, tabIndex } = useContext(TabsContext);
  const { id } = flows[tabIndex];
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
  const handleButtonClick = () => {
    // Create a file input element
    const input = document.createElement("input");
    input.type = "file";
    input.accept = suffixes.join(",");
    input.style.display = "none"; // Hidden from view
    input.multiple = false; // Allow only one file selection

    input.onchange = (e: Event) => {
      // Get the selected file
      const file = (e.target as HTMLInputElement).files?.[0];

      // Check if the file type is correct
      if (file && checkFileType(file.name)) {
        // Prepare the file for upload
        const formData = new FormData();
        formData.append("file", file);

        // Upload the file
        fetch(`/upload/${id}`, {
          method: "POST",
          body: formData,
        })
          .then((response) => response.json())
          .then((data) => {
            console.log("File uploaded successfully");
            // Get the file name from the response
            const { filename } = data;
            console.log("File name:", filename);

            // Update the state and callback with the name of the file
            // sets the value to the user
            setMyValue(file.name);
            onChange(file.name);
            // sets the value that goes to the backend
            onFileChange(filename);
          })
          .catch(() => {
            console.error("Error occurred while uploading file");
          });
      } else {
        // Show an error if the file type is not allowed
        setErrorData({
          title:
            "Please select a valid file. Only these file types are allowed:",
          list: fileTypes,
        });
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
      <div className="w-full flex items-center gap-3">
        <span
          onClick={handleButtonClick}
          className={
            "truncate block w-full text-gray-500 dark:text-gray-300 px-3 py-2 rounded-md border border-gray-300 dark:border-gray-700 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm" +
            (disabled ? " bg-gray-200" : "")
          }
        >
          {myValue !== "" ? myValue : "No file"}
        </span>
        <button onClick={handleButtonClick}>
          <DocumentMagnifyingGlassIcon className="w-8 h-8  hover:text-blue-600" />
        </button>
      </div>
    </div>
  );
}
