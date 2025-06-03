import { useFileHandler } from "@/modals/IOModal/components/chatView/chatInput/hooks/use-file-handler";

export const customUseFileHandler = (currentFlowId: string) => {
  return useFileHandler(currentFlowId);
};

export default customUseFileHandler;
