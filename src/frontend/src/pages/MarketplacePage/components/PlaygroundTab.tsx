import { useEffect } from "react";
import { v4 as uuid } from "uuid";
import { CustomIOModal } from "@/customization/components/custom-new-modal";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { type CookieOptions, getCookie, setCookie } from "@/utils/utils";

interface PlaygroundTabProps {
  publishedFlowData: any;
}

export default function PlaygroundTab({
  publishedFlowData,
}: PlaygroundTabProps) {
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const setPlaygroundPage = useFlowStore((state) => state.setPlaygroundPage);
  const setClientId = useUtilityStore((state) => state.setClientId);

  // Set up client_id cookie for playground tracking (required by backend)
  useEffect(() => {
    const clientId = getCookie("client_id");
    if (!clientId) {
      const newClientId = uuid();
      const cookieOptions: CookieOptions = {
        secure: window.location.protocol === "https:",
        sameSite: "strict",
      };
      setCookie("client_id", newClientId, cookieOptions);
      setClientId(newClientId);
    } else {
      setClientId(clientId);
    }
  }, [setClientId]);

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
      // Enable playground page mode - uses build_public_tmp endpoint and sessionStorage
      // Requires Genesis BFF to proxy these endpoints to AI Studio backend
      setPlaygroundPage(true);
    }

    // Cleanup: reset playground mode when component unmounts
    return () => {
      setPlaygroundPage(false);
    };
  }, [publishedFlowData, setCurrentFlow, setPlaygroundPage]);

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
        playgroundPage
      >
        <></>
      </CustomIOModal>
    </div>
  );
}
