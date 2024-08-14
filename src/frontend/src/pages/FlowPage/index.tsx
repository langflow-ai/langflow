import FeatureFlags from "@/../feature-config.json";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import { SaveChangesModal } from "@/modals/saveChangesModal";
import { useTypesStore } from "@/stores/typesStore";
import { customStringify } from "@/utils/reactflowUtils";
import { useEffect } from "react";
import { useBlocker, useNavigate, useParams } from "react-router-dom";
import FlowToolbar from "../../components/chatComponent";
import Header from "../../components/headerComponent";
import { useDarkStore } from "../../stores/darkStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import Page from "./components/PageComponent";
import ExtraSidebar from "./components/extraSidebarComponent";

export default function FlowPage({ view }: { view?: boolean }): JSX.Element {
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const currentSavedFlow = useFlowsManagerStore((state) => state.currentFlow);

  const changesNotSaved =
    customStringify(currentFlow) !== customStringify(currentSavedFlow);

  const blocker = useBlocker(changesNotSaved);
  const version = useDarkStore((state) => state.version);
  const setOnFlowPage = useFlowStore((state) => state.setOnFlowPage);
  const { id } = useParams();
  const navigate = useNavigate();
  useGetGlobalVariables();
  const saveFlow = useSaveFlow();

  const flows = useFlowsManagerStore((state) => state.flows);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const refreshFlows = useFlowsManagerStore((state) => state.refreshFlows);
  const setIsLoading = useFlowsManagerStore((state) => state.setIsLoading);
  const getTypes = useTypesStore((state) => state.getTypes);

  const handleSave = () => {
    saveFlow().then(() => (blocker.proceed ? blocker.proceed() : null));
  };

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (changesNotSaved) {
        event.preventDefault();
        event.returnValue = ""; // Required for Chrome
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [changesNotSaved, navigate]);

  // Set flow tab id
  useEffect(() => {
    const awaitgetTypes = async () => {
      if (flows && currentFlowId === "") {
        const isAnExistingFlow = flows.find((flow) => flow.id === id);

        if (!isAnExistingFlow) {
          navigate("/all");
          return;
        }

        setCurrentFlow(isAnExistingFlow);
      } else if (!flows) {
        setIsLoading(true);
        await refreshFlows();
        await getTypes();
        setIsLoading(false);
      }
    };
    awaitgetTypes();
  }, [id, flows]);

  useEffect(() => {
    setOnFlowPage(true);

    return () => {
      setOnFlowPage(false);
      setCurrentFlow();
    };
  }, [id]);

  return (
    <>
      <Header />
      <div className="flow-page-positioning">
        {currentFlow && (
          <div className="flex h-full overflow-hidden">
            {!view && <ExtraSidebar />}
            <main className="flex flex-1">
              {/* Primary column */}
              <div className="h-full w-full">
                <Page />
              </div>
              {!view && <FlowToolbar />}
            </main>
          </div>
        )}
        <a
          target={"_blank"}
          href="https://medium.com/logspace/langflow-datastax-better-together-1b7462cebc4d"
          className="langflow-page-icon"
        >
          {FeatureFlags.ENABLE_BRANDING && version && (
            <div className="mt-1">Langflow 🤝 DataStax</div>
          )}
          <div className={version ? "mt-2" : "mt-1"}>⛓️ v{version}</div>
        </a>
      </div>
      {blocker.state === "blocked" && (
        <SaveChangesModal
          onSave={handleSave}
          onCancel={() => (blocker.reset ? blocker.reset() : null)}
          onProceed={() => (blocker.proceed ? blocker.proceed() : null)}
        />
      )}
    </>
  );
}
