import { useFileHandler } from "@/components/core/playgroundComponent/components/chatView/chatInput/hooks/use-file-handler";

export const customUseFileHandler = (currentFlowId: string) => {
  return useFileHandler(currentFlowId);
};

export default customUseFileHandler;
