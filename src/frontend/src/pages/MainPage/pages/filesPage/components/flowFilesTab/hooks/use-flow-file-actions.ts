import { BASE_URL_API } from "@/constants/constants";
import { useDeleteFlowFile } from "@/controllers/API/queries/file-management/use-delete-flow-file";
import type { FlowFileInfo } from "@/controllers/API/queries/file-management/use-get-flow-files";
import { getFetchCredentials } from "@/customization/utils/get-fetch-credentials";
import useAlertStore from "@/stores/alertStore";

interface BulkDeleteCallbacks {
  onComplete: () => void;
}

export const useFlowFileActions = () => {
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const { mutate: deleteFile } = useDeleteFlowFile();

  const handleDownload = async (flowId: string, fileName: string) => {
    try {
      const response = await fetch(
        `${BASE_URL_API}files/download/${flowId}/${encodeURIComponent(fileName)}`,
        {
          headers: { Accept: "*/*" },
          credentials: getFetchCredentials(),
        },
      );
      if (!response.ok) {
        throw new Error(`Download failed with status ${response.status}`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", fileName);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error: unknown) {
      const message =
        error instanceof Error
          ? error.message
          : "An error occurred while downloading the file";
      setErrorData({
        title: "Error downloading file",
        list: [message],
      });
    }
  };

  const handleDeleteSingle = (file: FlowFileInfo, onComplete?: () => void) => {
    deleteFile(
      { flowId: file.flow_id, fileName: file.file_name },
      {
        onSuccess: () => {
          setSuccessData({ title: "File deleted successfully" });
          onComplete?.();
        },
        onError: (error: unknown) => {
          const message =
            error instanceof Error
              ? error.message
              : "An error occurred while deleting the file";
          setErrorData({
            title: "Error deleting file",
            list: [message],
          });
          onComplete?.();
        },
      },
    );
  };

  const handleBulkDelete = (
    files: FlowFileInfo[],
    { onComplete }: BulkDeleteCallbacks,
  ) => {
    let completed = 0;
    let errors = 0;
    const total = files.length;

    const finalize = () => {
      if (completed + errors !== total) return;

      if (errors === 0) {
        setSuccessData({
          title: `${completed} file${completed > 1 ? "s" : ""} deleted successfully`,
        });
      } else {
        setErrorData({
          title:
            completed === 0
              ? `Failed to delete ${errors} file${errors > 1 ? "s" : ""}`
              : `Deleted ${completed} file${completed > 1 ? "s" : ""}, failed to delete ${errors}`,
        });
      }

      onComplete();
    };

    for (const file of files) {
      deleteFile(
        { flowId: file.flow_id, fileName: file.file_name },
        {
          onSuccess: () => {
            completed++;
            finalize();
          },
          onError: () => {
            errors++;
            finalize();
          },
        },
      );
    }
  };

  return { handleDownload, handleDeleteSingle, handleBulkDelete };
};
