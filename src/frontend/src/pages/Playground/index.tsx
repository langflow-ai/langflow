import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import LoadingComponent from "../../components/loadingComponent";
import { getComponent } from "../../controllers/API";
import IOModal from "../../modals/IOModal";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import cloneFLowWithParent from "../../utils/storeUtils";

export default function PlaygroundPage() {
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const getFlowById = useFlowsManagerStore((state) => state.getFlowById);
  const setCurrentFlowId = useFlowsManagerStore(
    (state) => state.setCurrentFlowId,
  );
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const setNodes = useFlowStore((state) => state.setNodes);
  const setEdges = useFlowStore((state) => state.setEdges);
  const cleanFlowPool = useFlowStore((state) => state.CleanFlowPool);

  const { id } = useParams();
  const [loading, setLoading] = useState(true);
  async function getFlowData() {
    const res = await getComponent(id!);
    const newFlow = cloneFLowWithParent(res, res.id, false, true);
    return newFlow;
  }

  // Set flow tab id
  useEffect(() => {
    if (getFlowById(id!)) {
      setCurrentFlowId(id!);
    } else {
      getFlowData().then((flow) => {
        setCurrentFlow(flow);
      });
    }
  }, [id]);

  useEffect(() => {
    if (currentFlow) {
      setNodes(currentFlow?.data?.nodes ?? [], true);
      setEdges(currentFlow?.data?.edges ?? [], true);
      cleanFlowPool();
      setLoading(false);
    }
    return () => {
      setNodes([], true);
      setEdges([], true);
      cleanFlowPool();
    };
  }, [currentFlow]);

  return (
    <div className="flex h-full w-full flex-col items-center justify-center align-middle">
      {loading ? (
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
