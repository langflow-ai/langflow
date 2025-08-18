import { useGetDownloadFileV2 } from "@/controllers/API/queries/file-management";
import type { FileType } from "@/types/file_management";

interface SingleFileDownloadParams {
  id: string;
  filename: string;
  type: string;
}

export const useCustomHandleSingleFileDownload = (file: FileType) => {
  const { mutate: downloadFile } = useGetDownloadFileV2({
    id: file.id,
    filename: file.name,
    type: file.path.split(".").pop() || "",
  });

  const handleSingleDownload = (
    params?: SingleFileDownloadParams,
    setSuccessData?: (data: { title: string }) => void,
    setErrorData?: (data: { title: string; list: string[] }) => void,
  ) => {
    downloadFile();
  };

  return { handleSingleDownload };
};
