import { useContext, useEffect, useState } from "react";
import { alertContext } from "../../contexts/alertContext";
import { FileComponentType } from "../../types/components";
import { INPUT_STYLE } from "../../constants";
import { FileSearch2 } from "lucide-react";

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

  useEffect(() => {
    setMyValue(value);
  }, [value]);

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
        disabled ? "pointer-events-none cursor-not-allowed w-full" : "w-full"
      }
    >
      <div className="w-full flex items-center gap-3">
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
          {!editNode && (
            <FileSearch2 className="w-8 h-8  hover:text-ring" />
          )}
        </button>
      </div>
    </div>
  );
}
