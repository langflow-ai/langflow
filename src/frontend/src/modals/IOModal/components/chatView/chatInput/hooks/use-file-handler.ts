import { useState } from "react";
import { useChatFileUpload } from "@/shared/hooks/use-chat-file-upload";
import type { FilePreviewType } from "@/types/components";

export const useFileHandler = (
  currentFlowId: string,
  playgroundPage = false,
) => {
  const [files, setFiles] = useState<FilePreviewType[]>([]);
  const { handleFiles } = useChatFileUpload({
    currentFlowId,
    setFiles,
    playgroundPage,
  });

  return { files, setFiles, handleFiles };
};
