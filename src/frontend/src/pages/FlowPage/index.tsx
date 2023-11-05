import { useContext, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import Header from "../../components/headerComponent";
import { flowManagerContext } from "../../contexts/flowManagerContext";
import { FlowsContext } from "../../contexts/flowsContext";
import { getVersion } from "../../controllers/API";
import Page from "./components/PageComponent";

export default function FlowPage(): JSX.Element {
  const { setFlow } = useContext(flowManagerContext);
  const { flows, selectedFlowId, setFlowId } = useContext(FlowsContext);
  const { id } = useParams();

  // Set flow tab id
  useEffect(() => {
    setFlowId(id!);
    setFlow(flows.find((flow) => flow.id === id!)!);
  }, [id]);

  // Initialize state variable for the version
  const [version, setVersion] = useState("");
  useEffect(() => {
    getVersion().then((data) => {
      setVersion(data.version);
    });
  }, []);
  return (
    <>
      <Header />
      <div className="flow-page-positioning">
        {flows.length > 0 &&
          selectedFlowId !== "" &&
          flows.findIndex((flow) => flow.id === selectedFlowId) !== -1 && (
            <Page flow={flows.find((flow) => flow.id === selectedFlowId)!} />
          )}
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
