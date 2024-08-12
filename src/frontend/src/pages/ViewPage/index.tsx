import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import useFlowStore from "@/stores/flowStore";
import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import Page from "../FlowPage/components/PageComponent";

export default function ViewPage() {
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);

  const setOnFlowPage = useFlowStore((state) => state.setOnFlowPage);
  const { id } = useParams();
  const navigate = useNavigate();
  useGetGlobalVariables();

  const flows = useFlowsManagerStore((state) => state.flows);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  // Set flow tab id
  useEffect(() => {
    if (flows && currentFlowId === "") {
      const isAnExistingFlow = flows.find((flow) => flow.id === id);

      if (!isAnExistingFlow) {
        navigate("/all");
        return;
      }

      setCurrentFlow(isAnExistingFlow);
    }
  }, [id, flows]);

  useEffect(() => {
    setOnFlowPage(true);

    return () => {
      setOnFlowPage(false);
      setCurrentFlow();
    };
  }, [id]);

  return (
    <div className="flow-page-positioning">
      <Page view />
    </div>
  );
}
