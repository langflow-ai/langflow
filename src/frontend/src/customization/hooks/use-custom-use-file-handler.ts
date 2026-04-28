import { useFileHandler } from "@/modals/IOModal/components/chatView/chatInput/hooks/use-file-handler";

export const customUseFileHandler = (
  currentFlowId: string,
  playgroundPage = false,
) => {
  return useFileHandler(currentFlowId, playgroundPage);
};

export default customUseFileHandler;
