import { useEffect, useState } from "react";
import { useBlocker, useParams } from "react-router-dom";
import { SidebarProvider } from "@/components/ui/sidebar";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import { useGetTypes } from "@/controllers/API/queries/flows/use-get-types";
import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import { useIsMobile } from "@/hooks/use-mobile";
import { SaveChangesModal } from "@/modals/saveChangesModal";
import useAlertStore from "@/stores/alertStore";
import { useTypesStore } from "@/stores/typesStore";
import { customStringify } from "@/utils/reactflowUtils";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import {
  FlowSearchProvider,
  FlowSidebarComponent,
} from "./components/flowSidebarComponent";
import Page from "./components/PageComponent";

interface FlowPageProps {
  view?: boolean;
  flowId?: string;
  folderId?: string;
}

export default function FlowPage({ view, flowId: propFlowId, folderId: propFolderId }: FlowPageProps): JSX.Element {
  const types = useTypesStore((state) => state.types);

  useGetTypes({
    enabled: Object.keys(types).length <= 0,
  });

  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const currentSavedFlow = useFlowsManagerStore((state) => state.currentFlow);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const [isLoading, setIsLoading] = useState(false);

  const changesNotSaved =
    customStringify(currentFlow) !== customStringify(currentSavedFlow) &&
    (currentFlow?.data?.nodes?.length ?? 0) > 0;

  const isBuilding = useFlowStore((state) => state.isBuilding);
  const blocker = useBlocker(changesNotSaved || isBuilding);

  const setOnFlowPage = useFlowStore((state) => state.setOnFlowPage);
  const { id: paramId } = useParams();
  const navigate = useCustomNavigate();
  
  // Use flowId from props if provided, otherwise use URL param
  const id = propFlowId || paramId;
  const saveFlow = useSaveFlow();

  const flows = useFlowsManagerStore((state) => state.flows);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  const updatedAt = currentSavedFlow?.updated_at;
  const autoSaving = useFlowsManagerStore((state) => state.autoSaving);
  const stopBuilding = useFlowStore((state) => state.stopBuilding);

  const { mutateAsync: getFlow } = useGetFlow();

  const handleSave = () => {
    let saving = true;
    let proceed = false;
    setTimeout(() => {
      saving = false;
      if (proceed) {
        blocker.proceed && blocker.proceed();
        setSuccessData({
          title: "Flow saved successfully!",
        });
      }
    }, 1200);
    saveFlow()
      .then(() => {
        if (!autoSaving || saving === false) {
          blocker.proceed && blocker.proceed();
          setSuccessData({
            title: "Flow saved successfully!",
          });
        }
        proceed = true;
      })
      .catch((error) => {
        console.error("Failed to save flow:", error);
        // Even if save fails, we should still proceed with navigation
        blocker.proceed && blocker.proceed();
        proceed = true;
        // Optionally show an error message
        setSuccessData({
          title: "Failed to save flow, but navigation will continue",
        });
      });
  };

  const handleExit = () => {
    if (isBuilding) {
      // Do nothing, let the blocker handle it
    } else if (changesNotSaved) {
      if (blocker.proceed) blocker.proceed();
    } else {
      // Only navigate to /all if we're not using props (i.e., we're in a normal route context)
      if (!propFlowId) {
        navigate("/all");
      }
    }
  };

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (changesNotSaved || isBuilding) {
        event.preventDefault();
        event.returnValue = ""; // Required for Chrome
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [changesNotSaved, isBuilding]);

  // Set flow tab id
  useEffect(() => {
    const awaitgetTypes = async () => {
      if (flows && currentFlowId === "" && Object.keys(types).length > 0) {
        const isAnExistingFlow = flows.find((flow) => flow.id === id);

        if (!isAnExistingFlow) {
          // Only navigate to /all if we're not using props (i.e., we're in a normal route context)
          if (!propFlowId) {
            navigate("/all");
            return;
          }
          // If using props, try to load the flow directly
          if (id) {
            await getFlowToAddToCanvas(id);
          }
          return;
        }

        const isAnExistingFlowId = isAnExistingFlow.id;

        await getFlowToAddToCanvas(isAnExistingFlowId);
      }
    };
    awaitgetTypes();
  }, [id, flows, currentFlowId, types, propFlowId]);

  useEffect(() => {
    setOnFlowPage(true);

    return () => {
      setOnFlowPage(false);
      console.warn("unmounting");

      setCurrentFlow(undefined);
    };
  }, [id]);

  useEffect(() => {
    if (
      blocker.state === "blocked" &&
      autoSaving &&
      changesNotSaved &&
      !isBuilding
    ) {
      handleSave();
    }
  }, [blocker.state, isBuilding]);

  useEffect(() => {
    if (blocker.state === "blocked") {
      if (isBuilding) {
        stopBuilding();
      } else if (!changesNotSaved) {
        blocker.proceed && blocker.proceed();
      }
    }
  }, [blocker.state, isBuilding]);

  const getFlowToAddToCanvas = async (id: string) => {
    const flow = await getFlow({ id: id });
    setCurrentFlow(flow);
  };

  const isMobile = useIsMobile();

  return (
    <>
      <div className="flow-page-positioning">
        {currentFlow && (
          <div className="flex h-full overflow-hidden">
            <SidebarProvider
              width="17.5rem"
              defaultOpen={!isMobile}
              segmentedSidebar={ENABLE_NEW_SIDEBAR}
            >
              <FlowSearchProvider>
                <main className="flex w-full overflow-hidden">
                  <div className="h-full w-full">
                    <Page setIsLoading={setIsLoading} />
                  </div>
                </main>
                {!view && <FlowSidebarComponent isLoading={isLoading} />}
              </FlowSearchProvider>
            </SidebarProvider>
          </div>
        )}
      </div>
      {blocker.state === "blocked" && (
        <>
          {!isBuilding && currentSavedFlow && (
            <SaveChangesModal
              onSave={handleSave}
              onCancel={() => blocker.reset?.()}
              onProceed={handleExit}
              flowName={currentSavedFlow.name}
              lastSaved={
                updatedAt
                  ? new Date(updatedAt).toLocaleString("en-US", {
                      hour: "numeric",
                      minute: "numeric",
                      second: "numeric",
                      month: "numeric",
                      day: "numeric",
                    })
                  : undefined
              }
              autoSave={autoSaving}
            />
          )}
        </>
      )}
    </>
  );
}
