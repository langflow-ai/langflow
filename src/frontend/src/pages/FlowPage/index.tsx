import { useEffect, useState } from "react";
import { useBlocker, useParams } from "react-router-dom";
import { AnimatedConditional } from "@/components/ui/animated-close";
import { SidebarProvider } from "@/components/ui/sidebar";
import { SimpleSidebarProvider } from "@/components/ui/simple-sidebar";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import { useGetTypes } from "@/controllers/API/queries/flows/use-get-types";
import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import { useIsMobile } from "@/hooks/use-mobile";
import { SaveChangesModal } from "@/modals/saveChangesModal";
import useAlertStore from "@/stores/alertStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { useShortcutsStore } from "@/stores/shortcuts";
import { useTypesStore } from "@/stores/typesStore";
import { customStringify } from "@/utils/reactflowUtils";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import FlowBorderWrapperComponent from "./components/flowBorderWrapperComponent";
import {
  FlowSearchProvider,
  FlowSidebarComponent,
} from "./components/flowSidebarComponent";
import Page from "./components/PageComponent";
import { MemoizedSidebarTrigger } from "./components/PageComponent/MemoizedComponents";
import { PlaygroundSidebar } from "./components/PlaygroundSidebar";

export default function FlowPage({ view }: { view?: boolean }): JSX.Element {
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
  const { id } = useParams();
  const navigate = useCustomNavigate();
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
      if (flows && currentFlowId === "" && Object.keys(types).length > 0) {
        const isAnExistingFlow = flows.find((flow) => flow.id === id);

        if (!isAnExistingFlow) {
          navigate("/all");
          return;
        }

        const isAnExistingFlowId = isAnExistingFlow.id;

        await getFlowToAddToCanvas(isAnExistingFlowId);
      }
    };
    awaitgetTypes();
  }, [id, flows, currentFlowId, types]);

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

  const openPlayground = useShortcutsStore((state) => state.openPlayground);

  const isFullscreen = usePlaygroundStore((state) => state.isFullscreen);
  const setIsFullscreen = usePlaygroundStore((state) => state.setIsFullscreen);

  const isOpen = usePlaygroundStore((state) => state.isOpen);
  const setIsOpen = usePlaygroundStore((state) => state.setIsOpen);

  const onMaxWidth = (attemptedWidth: number, maxWidth: number) => {
    if (attemptedWidth > maxWidth + 50) {
      setIsFullscreen(true);
    }
  };

  return (
    <>
      <div className="flex h-full w-full">
        {currentFlow && (
          <FlowSearchProvider>
            <div className="flex h-full w-fit">
              <AnimatedConditional isOpen={!isFullscreen || !isOpen}>
                <SidebarProvider
                  width="17.5rem"
                  defaultOpen={!isMobile}
                  segmentedSidebar={ENABLE_NEW_SIDEBAR}
                >
                  {!view && <FlowSidebarComponent isLoading={isLoading} />}
                  <MemoizedSidebarTrigger />
                </SidebarProvider>
              </AnimatedConditional>
            </div>

            <SimpleSidebarProvider
              width="400px"
              minWidth={0.22}
              maxWidth={0.8}
              onMaxWidth={onMaxWidth}
              fullscreen={isFullscreen}
              defaultOpen={false}
              open={isOpen}
              onOpenChange={setIsOpen}
              shortcut={openPlayground}
            >
              <FlowBorderWrapperComponent setIsLoading={setIsLoading} />
            </SimpleSidebarProvider>
          </FlowSearchProvider>
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
