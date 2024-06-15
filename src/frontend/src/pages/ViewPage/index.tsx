import { useEffect } from "react";
import { useParams } from "react-router-dom";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import Page from "../FlowPage/components/PageComponent";

export default function ViewPage() {
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const setCurrentFlowId = useFlowsManagerStore(
    (state) => state.setCurrentFlowId,
  );
  const { id } = useParams();

  // Set flow tab id
  useEffect(() => {
    setCurrentFlowId(id!);
  }, [id]);

  return (
    <div className="flow-page-positioning">
      {currentFlow && <Page view flow={currentFlow} />}
    </div>
  );
}
