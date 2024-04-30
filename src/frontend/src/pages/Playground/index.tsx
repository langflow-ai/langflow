import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { getComponent } from "../../controllers/API";
import cloneFLowWithParent from "../../utils/storeUtils";
import LoadingComponent from "../../components/loadingComponent";
import useFlowStore from "../../stores/flowStore";
import IOModal from "../../modals/IOModal";

export default function PlaygroundPage() {
    const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
    const getFlowById = useFlowsManagerStore((state) => state.getFlowById);
    const setCurrentFlowId = useFlowsManagerStore((state) => state.setCurrentFlowId);
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
        console.log("id", id);
        if (getFlowById(id!)) {
            setCurrentFlowId(id!);
        }
        else {
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
        <div className="w-full h-full flex flex-col align-middle items-center justify-center">
            {loading ? <div><LoadingComponent remSize={24}></LoadingComponent></div> :
                <IOModal open={true}setOpen={()=>{}} isPlayground>
                    <></>
                </IOModal>}
        </div>
    )
}