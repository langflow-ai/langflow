import { useEffect } from "react";
import { useParams } from "react-router-dom";
import Page from "../FlowPage/components/PageComponent";
import useFlowsManagerStore from "../../stores/flowsManagerStore";

export default function ViewPage() {
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const setCurrentFlowId = useFlowsManagerStore((state) => state.setCurrentFlowId);
  const { id } = useParams();

  // Set flow tab id
  useEffect(() => {
    setCurrentFlowId(id!);
  }, [id]);

  return (
    <div className="flow-page-positioning">
        {currentFlow && (
          <Page view flow={currentFlow} />
        )}
    </div>
  );
}
