import { useStoreStore } from "@/stores/storeStore";
import { useEffect } from "react";
import { useParams } from "react-router-dom";
import LoadingComponent from "../../components/loadingComponent";
import { getComponent } from "../../controllers/API";
import IOModal from "../../modals/IOModal";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import cloneFLowWithParent from "../../utils/storeUtils";

export default function PlaygroundPage() {
  const getFlowById = useFlowsManagerStore((state) => state.getFlowById);
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

  // Set flow tab id
  useEffect(() => {
    if (flows) {
      const flow = getFlowById(id!);
      if (flow) {
        setCurrentFlow(flow);
      } else {
        if (validApiKey)
          getFlowData().then((flow) => {
            setCurrentFlow(flow);
          });
      }
    }
  }, [id, flows, validApiKey]);

  return (
    <div className="flex h-full w-full flex-col items-center justify-center align-middle">
      {!currentSavedFlow ? (
        <div>
          <LoadingComponent remSize={24}></LoadingComponent>
        </div>
      ) : (
        <IOModal open={true} setOpen={() => {}} isPlayground>
          <></>
        </IOModal>
      )}
    </div>
  );
}
