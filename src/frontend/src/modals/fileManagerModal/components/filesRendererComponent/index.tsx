import { FileType } from "@/types/file_management";
import FileRendererComponent from "./components/fileRendererComponent";

export default function FilesRendererComponent({
  files,
  handleFileSelect,
  selectedFiles,
  handleRemove,
  handleRename,
}: {
  files: FileType[];
  isSearch?: boolean;
  handleFileSelect?: (name: string) => void;
  selectedFiles?: string[];
  handleRemove?: (name: string) => void;
  handleRename?: (id: string, name: string) => void;
}) {
  return files.map((file, index) => (
    <FileRendererComponent
      key={index}
      file={file}
      handleFileSelect={handleFileSelect}
      selectedFiles={selectedFiles}
      handleRemove={handleRemove}
      handleRename={handleRename}
      index={index}
    />
  ));
}
