import { useGetRefreshFlows } from "@/controllers/API/queries/flows/use-get-refresh-flows";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { useTypesStore } from "@/stores/typesStore";
import { useEffect } from "react";
import { useParams } from "react-router-dom";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import Page from "../FlowPage/components/PageComponent";

export default function ViewPage() {
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);

  const { id } = useParams();
  const navigate = useCustomNavigate();

  const flows = useFlowsManagerStore((state) => state.flows);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const { mutateAsync: refreshFlows } = useGetRefreshFlows();
  const setIsLoading = useFlowsManagerStore((state) => state.setIsLoading);
  const getTypes = useTypesStore((state) => state.getTypes);
  const types = useTypesStore((state) => state.types);

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
        await refreshFlows({ get_all: true, header_flows: true });
        if (!types || Object.keys(types).length === 0) await getTypes();
        setIsLoading(false);
      }
    };
    awaitgetTypes();
  }, [id, flows]);

  return (
    <div className="flow-page-positioning">
      <Page view />
    </div>
  );
}
