import { useEffect } from "react";
import { useParams } from "react-router-dom";
import Header from "../../components/headerComponent";
import { useDarkStore } from "../../stores/darkStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import Page from "./components/PageComponent";

export default function FlowPage(): JSX.Element {
  const setCurrentFlowId = useFlowsManagerStore(
    (state) => state.setCurrentFlowId
  );
  const version = useDarkStore((state) => state.version);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const { id } = useParams();

  // Set flow tab id
  useEffect(() => {
    setCurrentFlowId(id!);
  }, [id]);

  return (
    <>
      <Header />
      <div className="flow-page-positioning">
        {currentFlow && <Page flow={currentFlow} />}
        <a
          target={"_blank"}
          href="https://logspace.ai/"
          className="logspace-page-icon"
        >
          {version && <div className="mt-1">⛓️ Langflow v{version}</div>}
          <div className={version ? "mt-2" : "mt-1"}>Created by Logspace</div>
        </a>
      </div>
    </>
  );
}
