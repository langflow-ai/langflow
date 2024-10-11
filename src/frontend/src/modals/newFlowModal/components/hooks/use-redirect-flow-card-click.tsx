import { useNavigate } from "react-router-dom";
import { track } from "../../../../customization/utils/analytics";
import useAddFlow from "../../../../hooks/flows/use-add-flow";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { FlowType } from "../../../../types/flow";
import { updateIds } from "../../../../utils/reactflowUtils";

export function useFlowCardClick() {
  const navigate = useNavigate();
  const addFlow = useAddFlow();

  const handleFlowCardClick = async (flow: FlowType, folderIdUrl: string) => {
    try {
      updateIds(flow.data!);
      const id = await addFlow({ flow });
      navigate(`/flow/${id}/folder/${folderIdUrl}`);
      track("New Flow Created", { template: `${flow.name} Template` });
    } catch (error) {
      console.error("Error handling flow card click:", error);
    }
  };

  return handleFlowCardClick;
}
