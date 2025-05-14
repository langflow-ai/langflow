import FileCard from "@/modals/IOModal/components/chatView/fileComponent/components/file-card";
import { fileCardPropsType } from "@/types/components";

export function CustomFileCard({
  fileName,
  path,
  fileType,
}: fileCardPropsType) {
  return <FileCard fileName={fileName} path={path} fileType={fileType} />;
}

export default CustomFileCard;
