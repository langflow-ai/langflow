import { useEffect } from "react";
import { useParams } from "react-router-dom";
import FlowToolbar from "../../components/chatComponent";
import Header from "../../components/headerComponent";
import { useDarkStore } from "../../stores/darkStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import Page from "./components/PageComponent";
import ExtraSidebar from "./components/extraSidebarComponent";
import useFlowStore from "../../stores/flowStore";

export default function FlowPage({ view }: { view?: boolean }): JSX.Element {
  const setCurrentFlowId = useFlowsManagerStore(
    (state) => state.setCurrentFlowId
  );
  const version = useDarkStore((state) => state.version);
  const setOnFlowPage = useFlowStore((state) => state.setOnFlowPage);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const { id } = useParams();

  // Set flow tab id
  useEffect(() => {
    setCurrentFlowId(id!);
    setOnFlowPage(true);
    
    return () => {
      setOnFlowPage(false);
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
                <Page flow={currentFlow} />
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
          {version && <div className="mt-1">Langflow 🤝 DataStax</div>}
          <div className={version ? "mt-2" : "mt-1"}>⛓️ v{version}</div>
        </a>
      </div>
    </>
  );
}
