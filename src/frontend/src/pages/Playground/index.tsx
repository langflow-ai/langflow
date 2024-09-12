import { useGetRefreshFlows } from "@/controllers/API/queries/flows/use-get-refresh-flows";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import { useStoreStore } from "@/stores/storeStore";
import { useTypesStore } from "@/stores/typesStore";
import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { getComponent } from "../../controllers/API";
import IOModal from "../../modals/IOModal";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import cloneFLowWithParent from "../../utils/storeUtils";

export default function PlaygroundPage() {
  const flows = useFlowsManagerStore((state) => state.flows);
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const currentSavedFlow = useFlowsManagerStore((state) => state.currentFlow);
  const validApiKey = useStoreStore((state) => state.validApiKey);

  const { id } = useParams();
  async function getFlowData() {
    const res = await getComponent(id!);
    const newFlow = cloneFLowWithParent(res, res.id, false, true);
    return newFlow;
  }

  const navigate = useCustomNavigate();

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
          if (validApiKey) {
            getFlowData().then((flow) => {
              setCurrentFlow(flow);
            });
          } else {
            navigate("/");
          }
        }
        setCurrentFlow(isAnExistingFlow);
      } else if (!flows) {
        setIsLoading(true);
        await refreshFlows(undefined);
        if (!types || Object.keys(types).length === 0) await getTypes();
        setIsLoading(false);
      }
    };
    awaitgetTypes();
  }, [id, flows, validApiKey]);

  useEffect(() => {
    if (id) track("Playground Page Loaded", { flowId: id });
  }, []);

  return (
    <div className="flex h-full w-full flex-col items-center justify-center align-middle">
      {currentSavedFlow && (
        <IOModal open={true} setOpen={() => {}} isPlayground>
          <></>
        </IOModal>
      )}
    </div>
  );
}
