
import { useNavigate } from "react-router-dom";
/// <reference types="vite-plugin-svgr/client" />
//@ts-ignore
import { ReactComponent as TransferFiles } from "../../assets/undraw_transfer_files_re_a2a9.svg"
//@ts-ignore
import { ReactComponent as BasicPrompt } from "../../assets/undraw_design_components_9vy6.svg"
//@ts-ignore
import { ReactComponent as ChatWithHistory } from "../../assets/undraw_mobile_messages_re_yx8w.svg"
//@ts-ignore
import { ReactComponent as Assistant } from "../../assets/undraw_team_collaboration_re_ow29.svg"
//@ts-ignore
import { ReactComponent as APIRequest } from "../../assets/undraw_real_time_analytics_re_yliv.svg"
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { FlowType } from "../../types/flow"
import { updateIds } from "../../utils/reactflowUtils";
import ShadTooltip from "../ShadTooltipComponent"
import { Card, CardContent, CardDescription, CardFooter, CardTitle } from "../ui/card"

export default function UndrawCardComponent({
    flow
}: { flow: FlowType }) {
    const addFlow = useFlowsManagerStore((state) => state.addFlow);
    const navigate = useNavigate();

    function selectImage() {
        switch (flow.name) {
            case "Data Ingestion":
                return <TransferFiles style={{ width: '80%', height: '80%', preserveAspectRatio: 'xMidYMid meet' }} />
            case "Basic Prompting":
                return <BasicPrompt style={{ width: '80%', height: '80%', preserveAspectRatio: 'xMidYMid meet' }} />
                case "Chat with memory":
                    return <ChatWithHistory style={{ width: '70%', height: '70%', preserveAspectRatio: 'xMidYMid meet' }} />    
                case "API requests":
                    return <APIRequest style={{ width: '70%', height: '70%', preserveAspectRatio: 'xMidYMid meet' }} />
                case "Assistant":
                    return <Assistant style={{ width: '80%', height: '80%', preserveAspectRatio: 'xMidYMid meet' }} />
                    default:
                return <TransferFiles style={{ width: '80%', height: '80%', preserveAspectRatio: 'xMidYMid meet' }} />
        }
    }

    return (
        <Card onClick={() => {
            updateIds(flow.data!);
            addFlow(true, flow).then((id) => {
                navigate("/flow/" + id);
            });
        }} className="pt-4 w-80 h-64 cursor-pointer bg-background">
            <CardContent className="w-full h-full">
                <div className="rounded-md p-1 bg-muted w-full h-full flex flex-col items-center align-middle justify-center">
                    {selectImage()}
                </div>
            </CardContent>
            <CardDescription className="px-6 pb-4">
                <CardTitle className="text-primary text-lg">{flow.name}</CardTitle>
            </CardDescription>
        </Card>
    )
}