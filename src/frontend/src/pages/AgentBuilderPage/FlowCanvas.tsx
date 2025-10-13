import { useEffect, useState } from "react";
import { SidebarProvider } from "@/components/ui/sidebar";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import { useGetTypes } from "@/controllers/API/queries/flows/use-get-types";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useTypesStore } from "@/stores/typesStore";
import Page from "../FlowPage/components/PageComponent";
import { FlowSearchProvider } from "../FlowPage/components/flowSidebarComponent";

interface FlowCanvasProps {
  flowId: string;
  folderId: string;
}

export default function FlowCanvas({ flowId, folderId }: FlowCanvasProps) {
  const [isLoading, setIsLoading] = useState(false);
  const types = useTypesStore((state) => state.types);
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const setOnFlowPage = useFlowStore((state) => state.setOnFlowPage);
  const flows = useFlowsManagerStore((state) => state.flows);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  const { mutateAsync: getFlow } = useGetFlow();

  useGetTypes({
    enabled: Object.keys(types).length <= 0,
  });

  // Similar to FlowPage's getFlowToAddToCanvas
  const getFlowToAddToCanvas = async (id: string) => {
    const flow = await getFlow({ id: id });
    setCurrentFlow(flow);
  };

  // Similar to FlowPage's flow loading logic
  useEffect(() => {
    const awaitgetTypes = async () => {
      if (flows && currentFlowId === "" && Object.keys(types).length > 0) {
        const isAnExistingFlow = flows.find((flow) => flow.id === flowId);

        if (isAnExistingFlow) {
          const isAnExistingFlowId = isAnExistingFlow.id;
          await getFlowToAddToCanvas(isAnExistingFlowId);
        }
      }
    };
    awaitgetTypes();
  }, [flowId, flows, currentFlowId, types]);

  useEffect(() => {
    setOnFlowPage(true);

    return () => {
      setOnFlowPage(false);
    };
  }, [flowId, setOnFlowPage]);

  return (
    <div className="h-full w-full">
      {currentFlow && (
        <div className="flex h-full overflow-hidden">
          <SidebarProvider width="0" defaultOpen={false}>
            <FlowSearchProvider>
              <main className="flex w-full overflow-hidden">
                <div className="h-full w-full">
                  <Page view={true} setIsLoading={setIsLoading} />
                </div>
              </main>
            </FlowSearchProvider>
          </SidebarProvider>
        </div>
      )}
      {!currentFlow && (
        <div className="flex h-full w-full items-center justify-center">
          <div className="text-muted-foreground">Loading flow...</div>
        </div>
      )}
    </div>
  );
}