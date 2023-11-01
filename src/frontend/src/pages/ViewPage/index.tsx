import { useContext, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { FlowsContext } from "../../contexts/flowsContext";
import { getVersion } from "../../controllers/API";
import Page from "../FlowPage/components/PageComponent";

export default function ViewPage() {
  const { flows, tabId, setTabId } = useContext(FlowsContext);
  const { id } = useParams();

  // Set flow tab id
  useEffect(() => {
    setTabId(id!);
  }, [id]);

  // Initialize state variable for the version
  const [version, setVersion] = useState("");
  useEffect(() => {
    getVersion().then((data) => {
      setVersion(data.version);
    });
  }, []);

  return (
    <div className="flow-page-positioning">
      {flows.length > 0 &&
        tabId !== "" &&
        flows.findIndex((flow) => flow.id === tabId) !== -1 && (
          <Page view flow={flows.find((flow) => flow.id === tabId)!} />
        )}
    </div>
  );
}
