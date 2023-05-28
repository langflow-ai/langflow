import { DocumentMagnifyingGlassIcon } from "@heroicons/react/24/outline";
import { useContext, useEffect, useState } from "react";
import { alertContext } from "../../contexts/alertContext";
import { FileComponentType } from "../../types/components";

export default function InputDirectoryComponent({
  value,
  onChange,
  disabled,
  suffixes,
  fileTypes,
  onFileChange,
}: FileComponentType) {
  const [myValue, setMyValue] = useState(value);
  const { setErrorData } = useContext(alertContext);
  useEffect(() => {
    if (disabled) {
      setMyValue("");
      onChange("");
      onFileChange("");
    }
  }, [disabled, onChange]);

  function attachFiles(files) {
    onFileChange(files);
  }

  function checkFileType(fileName: string): boolean {
    for (let index = 0; index < suffixes.length; index++) {
      if (fileName.endsWith(suffixes[index])) {
        return true;
      }
    }
    return false;
  }

  const handleDirectoryButtonClick = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = suffixes.join(",");
    input.style.display = "none";
    input.multiple = true;
    input.webkitdirectory = true;
    input.onchange = (e: Event) => {
      const filesArray = [];
      const inputElement = e.target as HTMLInputElement;
      console.log(inputElement.webkitEntries); // Not working
      const files = (e.target as HTMLInputElement).files;
      const directory = (e.target as HTMLInputElement).dirName; // Not working

      console.log(directory);
      if (files) {
        for (let index = 0; index < files.length; index++) {
          const file = files[index];
          if (checkFileType(file.name)) {
            console.log("going in: ", file);
            filesArray.push(file);
          }
        }
        if (filesArray.length > 0) {
            setMyValue(filesArray[0].webkitRelativePath);
            onChange(filesArray[0].webkitRelativePath);
            attachFiles(filesArray[0].webkitRelativePath);
        } else {
            setErrorData({
                title:
                  "Please select a valid directory. Only directories containing files with these file types are allowed:",
                list: fileTypes,
              });
        }
      }
    };
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
          onClick={handleDirectoryButtonClick}
          className={
            "truncate block w-full text-gray-500 dark:text-gray-300 px-3 py-2 rounded-md border border-gray-300 dark:border-gray-700 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm" +
            (disabled ? " bg-gray-200" : "")
          }
        >
          {myValue !== "" ? myValue : "No directory"}
        </span>
        <button onClick={handleDirectoryButtonClick}>
          <DocumentMagnifyingGlassIcon className="w-8 h-8  hover:text-blue-600" />
        </button>
      </div>
    </div>
  );
}
