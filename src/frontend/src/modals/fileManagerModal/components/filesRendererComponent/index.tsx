import type { FileType } from "@/types/file_management";
import FileRendererComponent from "./components/fileRendererComponent";

export default function FilesRendererComponent({
  files,
  handleFileSelect,
  selectedFiles,
  handleRemove,
  handleRename,
  isShiftPressed,
}: {
  files: FileType[];
  isSearch?: boolean;
  handleFileSelect?: (name: string, index: number) => void;
  selectedFiles?: string[];
  handleRemove?: (name: string) => void;
  handleRename?: (id: string, name: string) => void;
  isShiftPressed?: boolean;
}) {
  return files.map((file, index) => (
    <FileRendererComponent
      key={index}
      file={file}
      handleFileSelect={
        handleFileSelect ? (name) => handleFileSelect(name, index) : undefined
      }
      selectedFiles={selectedFiles}
      handleRemove={handleRemove}
      handleRename={handleRename}
      isShiftPressed={isShiftPressed}
      index={index}
    />
  ));
}
