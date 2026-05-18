import {
  useCallback,
  type ChangeEvent,
  type Dispatch,
  type SetStateAction,
} from "react";
import type { AxiosError } from "axios";
import ShortUniqueId from "short-unique-id";
import {
  FS_ERROR_TEXT,
  SN_ERROR_TEXT,
} from "@/constants/file-upload-constants";
import { ENABLE_FILES_ON_PLAYGROUND } from "@/customization/feature-flags";
import { usePostUploadFile } from "@/controllers/API/queries/files/use-post-upload-file";
import useFileSizeValidator from "@/shared/hooks/use-file-size-validator";
import { isAllowedChatAttachmentFile } from "@/utils/file-validation";
import useAlertStore from "@/stores/alertStore";
import type { FilePreviewType } from "@/types/components";
import { useTranslation } from "react-i18next";

interface UseChatFileUploadParams {
  currentFlowId: string;
  setFiles: Dispatch<SetStateAction<FilePreviewType[]>>;
  playgroundPage?: boolean;
}

export const useChatFileUpload = ({
  currentFlowId,
  setFiles,
  playgroundPage = false,
}: UseChatFileUploadParams) => {
  const { t } = useTranslation();
  const { mutate } = usePostUploadFile();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { validateFileSize } = useFileSizeValidator();

  const isUploadEnabled = !playgroundPage || ENABLE_FILES_ON_PLAYGROUND;

  const uploadFile = useCallback(
    (file: File) => {
      if (!isUploadEnabled) {
        return;
      }

      if (!isAllowedChatAttachmentFile(file)) {
        setErrorData({
          title: "Error uploading file",
          list: [FS_ERROR_TEXT, SN_ERROR_TEXT],
        });
        return;
      }

      const uid = new ShortUniqueId();
      const id = uid.randomUUID(10);
      const type = file.type.split("/")[0] || "file";

      setFiles((prevFiles) => [
        ...prevFiles,
        { file, loading: true, error: false, id, type },
      ]);

      mutate(
        { file, id: currentFlowId },
        {
          onSuccess: (data) => {
            setFiles((prev) => {
              const newFiles = [...prev];
              const updatedIndex = newFiles.findIndex((f) => f.id === id);

              if (updatedIndex === -1) {
                return prev;
              }

              newFiles[updatedIndex] = {
                ...newFiles[updatedIndex],
                loading: false,
                path: data.file_path,
              };
              return newFiles;
            });
          },
          onError: (error: AxiosError<{ detail?: string }>) => {
            setFiles((prev) => {
              const newFiles = [...prev];
              const updatedIndex = newFiles.findIndex((f) => f.id === id);

              if (updatedIndex === -1) {
                return prev;
              }

              newFiles[updatedIndex] = {
                ...newFiles[updatedIndex],
                loading: false,
                error: true,
              };
              return newFiles;
            });

            setErrorData({
              title: "Error uploading file",
              list: [t("misc.fsErrorText"), SN_ERROR_TEXT],
            });
          },
        },
      );
    },
    [currentFlowId, isUploadEnabled, mutate, setErrorData, setFiles],
  );

  const handleFiles = useCallback(
    (uploadedFiles: FileList | null) => {
      if (!isUploadEnabled) {
        return;
      }

      if (!uploadedFiles || uploadedFiles.length === 0) {
        return;
      }

      const file = uploadedFiles[0];

      try {
        validateFileSize(file);
      } catch (error) {
        if (error instanceof Error) {
          setErrorData({ title: error.message });
        }
        return;
      }

      uploadFile(file);
    },
    [isUploadEnabled, setErrorData, uploadFile, validateFileSize],
  );

  const handleFileChange = useCallback(
    (event: ChangeEvent<HTMLInputElement> | ClipboardEvent) => {
      if (!isUploadEnabled) {
        if ("target" in event && event.target instanceof HTMLInputElement) {
          event.target.value = "";
        }
        return;
      }

      if ("clipboardData" in event) {
        const items = event.clipboardData?.items;
        if (!items) {
          return;
        }

        for (let i = 0; i < items.length; i++) {
          const file = items[i].getAsFile();
          if (file) {
            try {
              validateFileSize(file);
            } catch (error) {
              if (error instanceof Error) {
                setErrorData({ title: error.message });
              }
              return;
            }
            uploadFile(file);
            return;
          }
        }

        return;
      }

      const fileInput = event.target as HTMLInputElement;
      handleFiles(fileInput.files);
      fileInput.value = "";
    },
    [handleFiles, isUploadEnabled, setErrorData, uploadFile, validateFileSize],
  );

  return { handleFiles, handleFileChange };
};
