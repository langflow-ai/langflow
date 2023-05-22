import { DocumentMagnifyingGlassIcon } from "@heroicons/react/24/outline";
import { useContext, useEffect, useState } from "react";
import { alertContext } from "../../contexts/alertContext";
import { FileComponentType } from "../../types/components";

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
  useEffect(() => {
    if (disabled) {
      setMyValue("");
      onChange("");
      onFileChange("");
    }
  }, [disabled, onChange]);

  function attachFile(fileReadEvent: ProgressEvent<FileReader>) {
    fileReadEvent.preventDefault();
    const file = fileReadEvent.target.result;
    onFileChange(file as string);
  }

  function checkFileType(fileName: string): boolean {
    for (let index = 0; index < suffixes.length; index++) {
      if (fileName.endsWith(suffixes[index])) {
        return true;
      }
    }
    return false;
  }

  const handleButtonClick = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = suffixes.join(",");
    input.style.display = "none";
    input.multiple = false;
    input.onchange = (e: Event) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      const fileData = new FileReader();
      fileData.onload = attachFile;
      if (file && checkFileType(file.name)) {
        fileData.readAsDataURL(file);
        setMyValue(file.name);
        onChange(file.name);
      } else {
        setErrorData({
          title:
            "Please select a valid file. Only files this files are allowed:",
          list: fileTypes,
        });
      }
    };
    input.click();
  };

  return (
    <div
      className={
        disabled ? "pointer-events-none w-full cursor-not-allowed" : "w-full"
      }
    >
      <div className="flex w-full items-center gap-3">
        <span
          onClick={handleButtonClick}
          className={
            "block w-full truncate rounded-md border border-gray-300 px-3 py-2 text-gray-500 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:border-gray-700 dark:text-gray-300 sm:text-sm" +
            (disabled ? " bg-gray-200" : "")
          }
        >
          {myValue !== "" ? myValue : "No file"}
        </span>
        <button onClick={handleButtonClick}>
          <DocumentMagnifyingGlassIcon className="h-8 w-8  hover:text-blue-600" />
        </button>
      </div>
    </div>
  );
}
