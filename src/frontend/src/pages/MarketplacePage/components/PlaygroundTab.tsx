import { useEffect } from "react";
import { CustomIOModal } from "@/customization/components/custom-new-modal";
import useFlowsManagerStore from "@/stores/flowsManagerStore";

interface PlaygroundTabProps {
  publishedFlowData: any;
}

export default function PlaygroundTab({
  publishedFlowData,
}: PlaygroundTabProps) {
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);

  useEffect(() => {
    if (publishedFlowData) {
      // Set up the flow in the store for playground mode
      const flowData = {
        id: publishedFlowData.flow_id,
        name: publishedFlowData.flow_name || "Flow",
        data: publishedFlowData.flow_data,
        description: publishedFlowData.description || "",
      };
      setCurrentFlow(flowData as any);
      // Don't set playgroundPage to true - that triggers build_public_tmp endpoint
      // which doesn't exist in genesis-bff. Regular playground uses /run/ endpoint.
    }
  }, [publishedFlowData, setCurrentFlow]);

  // Don't render if no flow data
  if (!publishedFlowData) {
    return (
      <div className="flex h-full w-full items-center justify-center p-8 text-muted-foreground">
        Loading playground...
      </div>
    );
  }

  return (
    <div className="flex h-full w-full flex-col">
      <CustomIOModal
        open={true}
        setOpen={() => {}}
        isPlayground
      >
        <></>
      </CustomIOModal>
    </div>
  );
}
