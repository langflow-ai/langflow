import { useState } from "react";
import { useTranslation } from "react-i18next";
import ShortUniqueId from "short-unique-id";
import {
  ALLOWED_IMAGE_INPUT_EXTENSIONS,
  SN_ERROR_TEXT,
} from "@/constants/constants";
import { usePostUploadFile } from "@/controllers/API/queries/files/use-post-upload-file";
import useAlertStore from "@/stores/alertStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { FilePreviewType } from "@/types/components";
import { formatFileSize } from "@/utils/stringManipulation";

export const useFileHandler = (currentFlowId: string) => {
  const { t } = useTranslation();
  const [files, setFiles] = useState<FilePreviewType[]>([]);
  const { mutate } = usePostUploadFile();
  const { setErrorData } = useAlertStore();
  const maxFileSizeUpload = useUtilityStore((state) => state.maxFileSizeUpload);

  const handleFiles = (uploadedFiles: FileList) => {
    if (uploadedFiles) {
      const file = uploadedFiles[0];
      const fileExtension = file.name.split(".").pop()?.toLowerCase();
      if (file.size > maxFileSizeUpload) {
        setErrorData({
          title: t("errors.fileTooLarge", { maxSizeMB: formatFileSize(maxFileSizeUpload) }),
        });
        return;
      }

      if (
        !fileExtension ||
        !ALLOWED_IMAGE_INPUT_EXTENSIONS.includes(fileExtension)
      ) {
        console.error("Error uploading file");
        setErrorData({
          title: "Error uploading file",
          list: [t("misc.fsErrorText"), SN_ERROR_TEXT],
        });
        return;
      }
      const uid = new ShortUniqueId();
      const newId = uid.randomUUID(3);

      const type = file.type.split("/")[0];
      const blob = file;

      setFiles((prevFiles) => [
        ...prevFiles,
        { file: blob, loading: true, error: false, id: newId, type },
      ]);

      mutate(
        { file: blob, id: currentFlowId },
        {
          onSuccess: (data) => {
            setFiles((prev) => {
              const newFiles = [...prev];
              const updatedIndex = newFiles.findIndex(
                (file) => file.id === newId,
              );
              newFiles[updatedIndex].loading = false;
              newFiles[updatedIndex].path = data.file_path;
              return newFiles;
            });
          },
          onError: (error) => {
            setFiles((prev) => {
              const newFiles = [...prev];
              const updatedIndex = newFiles.findIndex(
                (file) => file.id === newId,
              );
              newFiles[updatedIndex].loading = false;
              newFiles[updatedIndex].error = true;
              return newFiles;
            });
            setErrorData({
              title: "Error uploading file",
              list: [error.response?.data?.detail],
            });
          },
        },
      );
    }
  };

  return { files, setFiles, handleFiles };
};
