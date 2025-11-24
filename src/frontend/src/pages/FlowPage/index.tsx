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
  readOnly?: boolean;
  viewOnly?: boolean;
  flowId?: string;
  folderId?: string;
}

export default function FlowPage({
  view,
  readOnly,
  viewOnly,
  flowId: propFlowId,
  folderId: propFolderId,
}: FlowPageProps): JSX.Element {
  const types = useTypesStore((state) => state.types);

  useGetTypes({
    enabled: Object.keys(types).length <= 0,
  });

  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const currentSavedFlow = useFlowsManagerStore((state) => state.currentFlow);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const [isLoading, setIsLoading] = useState(false);

  // Skip change tracking for read-only/view mode
  const changesNotSaved =
    !view &&
    !readOnly &&
    customStringify(currentFlow) !== customStringify(currentSavedFlow) &&
    (currentFlow?.data?.nodes?.length ?? 0) > 0;

  const isBuilding = useFlowStore((state) => state.isBuilding);
  // Don't block navigation in view/read-only mode
  const blocker = useBlocker(
    view || readOnly ? false : changesNotSaved || isBuilding
  );

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
        // Check if this is just a "flow not ready" guard vs actual error
        const isFlowNotReady = error?.message?.includes(
          "Cannot save flow without ID"
        );

        if (!isFlowNotReady) {
          // Actual save error - show error message
          console.error("Failed to save flow:", error);
          setSuccessData({
            title: "Failed to save flow, but navigation will continue",
          });
        }

        // Even if save fails, we should still proceed with navigation
        blocker.proceed && blocker.proceed();
        proceed = true;
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
    // Skip beforeunload warning in view/read-only mode
    if (view || readOnly) return;

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
  }, [changesNotSaved, isBuilding, view, readOnly]);

  // Set flow tab id
  useEffect(() => {
    const awaitgetTypes = async () => {
      if (flows && currentFlowId === "" && Object.keys(types).length > 0) {
        const isAnExistingFlow = flows.find((flow) => flow.id === id);

        if (!isAnExistingFlow) {
          // Flow not in local state, try to fetch it from backend API
          if (id) {
            try {
              // Try to load the flow from backend (this will check permissions)
              await getFlowToAddToCanvas(id);
              // If successful, the flow will be loaded and displayed
              // No redirect needed - backend permission check passed
            } catch (error: any) {
              // Backend returned error (404 = not found, 403 = no permission)
              // Only NOW redirect to /all
              console.error("Failed to load flow:", {
                flowId: id,
                status: error?.response?.status,
                message: error?.response?.data?.detail || error?.message,
              });
              if (!propFlowId) {
                navigate("/all");
              }
            }
          } else {
            // No ID provided, redirect
            if (!propFlowId) {
              navigate("/all");
            }
          }
          return;
        }

        // Flow exists in local state, load it normally
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
    // Skip auto-save in view/read-only mode
    if (view || readOnly) return;

    if (
      blocker.state === "blocked" &&
      autoSaving &&
      changesNotSaved &&
      !isBuilding &&
      !currentFlow?.locked // Don't autosave locked flows
    ) {
      // Prevent auto-save if current flow doesn't have an ID yet
      if (!currentFlow?.id) {
        return;
      }
      handleSave();
    }
  }, [blocker.state, isBuilding, view, readOnly]);

  useEffect(() => {
    // Skip blocker logic in view/read-only mode
    if (view || readOnly) return;

    if (blocker.state === "blocked") {
      if (isBuilding) {
        stopBuilding();
      } else if (!changesNotSaved || currentFlow?.locked) {
        // Proceed if no changes OR if flow is locked (don't save locked flows)
        blocker.proceed && blocker.proceed();
      }
    }
  }, [blocker.state, isBuilding, view, readOnly]);

  const getFlowToAddToCanvas = async (id: string) => {
    try {
      const flow = await getFlow({ id: id });

      // Ensure flow has an ID before setting it
      if (!flow || !flow.id) {
        console.error("Loaded flow is missing ID");
        throw new Error("Flow data is incomplete - missing ID");
      }

      setCurrentFlow(flow);
    } catch (error) {
      console.error("Failed to load flow:", error);
      throw error;
    }
  };

  const isMobile = useIsMobile();

  return (
    <>
      <div className="flow-page-positioning bg-white">
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
                    <Page
                      view={view}
                      readOnly={readOnly}
                      viewOnly={viewOnly}
                      setIsLoading={setIsLoading}
                    />
                  </div>
                </main>
                {!view && !viewOnly && (
                  <FlowSidebarComponent isLoading={isLoading} />
                )}
              </FlowSearchProvider>
            </SidebarProvider>
          </div>
        )}
      </div>
      {!view && !readOnly && blocker.state === "blocked" && (
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
