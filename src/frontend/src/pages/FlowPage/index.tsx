import { SidebarProvider } from "@/components/ui/sidebar";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import { useGetRefreshFlows } from "@/controllers/API/queries/flows/use-get-refresh-flows";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import { useIsMobile } from "@/hooks/use-mobile";
import { SaveChangesModal } from "@/modals/saveChangesModal";
import useAlertStore from "@/stores/alertStore";
import { useTypesStore } from "@/stores/typesStore";
import { customStringify } from "@/utils/reactflowUtils";
import { useEffect } from "react";
import { useBlocker, useParams } from "react-router-dom";
import { useDarkStore } from "../../stores/darkStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import Page from "./components/PageComponent";
import { FlowSidebarComponent } from "./components/flowSidebarComponent";

export default function FlowPage({ view }: { view?: boolean }): JSX.Element {
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const currentSavedFlow = useFlowsManagerStore((state) => state.currentFlow);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const changesNotSaved =
    customStringify(currentFlow) !== customStringify(currentSavedFlow) &&
    (currentFlow?.data?.nodes?.length ?? 0) > 0;

  const isBuilding = useFlowStore((state) => state.isBuilding);
  const blocker = useBlocker(changesNotSaved || isBuilding);

  const version = useDarkStore((state) => state.version);
  const setOnFlowPage = useFlowStore((state) => state.setOnFlowPage);
  const { id } = useParams();
  const navigate = useCustomNavigate();
  const saveFlow = useSaveFlow();

  const flows = useFlowsManagerStore((state) => state.flows);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  const flowToCanvas = useFlowsManagerStore((state) => state.flowToCanvas);

  const { mutateAsync: refreshFlows } = useGetRefreshFlows();
  const setIsLoading = useFlowsManagerStore((state) => state.setIsLoading);
  const getTypes = useTypesStore((state) => state.getTypes);
  const types = useTypesStore((state) => state.types);

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
    saveFlow().then(() => {
      if (!autoSaving || saving === false) {
        blocker.proceed && blocker.proceed();
        setSuccessData({
          title: "Flow saved successfully!",
        });
      }
      proceed = true;
    });
  };

  const handleExit = () => {
    if (isBuilding) {
      // Do nothing, let the blocker handle it
    } else if (changesNotSaved) {
      if (blocker.proceed) blocker.proceed();
    } else {
      navigate("/all");
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
      if (flows && currentFlowId === "") {
        const isAnExistingFlow = flows.find((flow) => flow.id === id);

        if (!isAnExistingFlow) {
          navigate("/all");
          return;
        }

        const isAnExistingFlowId = isAnExistingFlow.id;

        flowToCanvas
          ? setCurrentFlow(flowToCanvas)
          : getFlowToAddToCanvas(isAnExistingFlowId);
      } else if (!flows) {
        setIsLoading(true);
        await refreshFlows({ get_all: true, header_flows: true });
        if (!types || Object.keys(types).length === 0) await getTypes();
        setIsLoading(false);
      }
    };
    awaitgetTypes();
  }, [id, flows, currentFlowId, flowToCanvas]);

  useEffect(() => {
    setOnFlowPage(true);

    return () => {
      setOnFlowPage(false);
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
            <SidebarProvider width="17.5rem" defaultOpen={!isMobile}>
              {!view && <FlowSidebarComponent />}
              <main className="flex flex-1">
                <div className="h-full w-full">
                  <Page />
                </div>
              </main>
            </SidebarProvider>
          </div>
        )}
        {/* {ENABLE_BRANDING && version && (
          <a
            target={"_blank"}
            href="https://medium.com/logspace/langflow-datastax-better-together-1b7462cebc4d"
            className="langflow-page-icon"
          >
            <div className="mt-1">Langflow 🤝 DataStax</div>

            <div className={version ? "mt-2" : "mt-1"}>⛓️ v{version}</div>
          </a>
        )} */}
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
